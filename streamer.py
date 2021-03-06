# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from concurrent import futures
from time import sleep
import time
import hashlib

WINDOW_SIZE = 40
DATS_B4_ACK = 2

MS_FOR_SENDER = 30

class Streamer:

    global WINDOW_SIZE
    global DATS_B4_ACK

    global MS_FOR_SENDER

    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        self.current_seq = 0 # The current packetnum to be sent and to be expected
        self.last_ACK = -1 # The last packetnum that was acked
        self.sender_index = 0 # For labeling the packets to be sent

        self.data_to_send = {} # Buffer to send items
        self.buffer = {} # Buffer for recieved items

        self.listening = True
        self.FIN = False
        self.FINACK = False

        self.sending = False
        self.receiving = False

        self.wait_to_send = 0

        self.last_sent = 0
        self.send_window = 0

        self.timing = True

        executor = futures.ThreadPoolExecutor(max_workers=2)
        executor.submit(self.listen)
        executor.submit(self.sender)

    def send(self, data_bytes: bytes) -> None:

        while self.receiving:
            sleep(0.01)

        self.sending = True

        header_length = 50
        max_packet_length = 1472

        data_length = max_packet_length - header_length

        for data in self.break_string(data_bytes, data_length):
            sleep(0.05)
            h = hashlib.md5()

            packet = (' DAT ' + str(self.current_seq) + '~').encode() + data
            h.update(packet)
            packet = h.hexdigest().encode() + packet
            #print("Sent: %s at %s" % (packet, self.millis()))
            self.data_to_send[self.current_seq] = packet

            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            self.send_window += 1

            if self.send_window > WINDOW_SIZE:
                self.last_sent = self.current_seq - WINDOW_SIZE

            while self.send_window > WINDOW_SIZE:
                self.send_window = self.current_seq - self.last_ACK

            self.current_seq += 1

        self.sending = False

    def sender(self) -> None:
        ms = 0
        while self.timing:
            if self.last_sent > self.last_ACK:
                sleep(0.01)
                ms += 1
                if ms >= MS_FOR_SENDER:
                    self.resend(self.last_sent)
                    ms = 0
            elif self.last_sent <= self.last_ACK:
                self.last_sent = self.last_ACK + 1
            if self.FINACK:
                break

    def resend(self, packet_num: int) -> None:
        try:
            packet = self.data_to_send[packet_num]
        except Exception as e:
            pass
        else:
            #print("Resent: %s at %s" % (packet, self.millis()))
            self.socket.sendto(packet, (self.dst_ip, self.dst_port))


    def send_ACK(self, number: int) -> None:
        h = hashlib.md5()
        acknowledgement = (' ACK ' + str(number) + '~').encode()
        h.update(acknowledgement)
        acknowledgement = h.hexdigest().encode() + acknowledgement
        #print("Sent: %s at %s" % (acknowledgement, self.millis()))
        self.socket.sendto(acknowledgement, (self.dst_ip, self.dst_port))

    def send_FIN(self) -> None:
        h = hashlib.md5()
        finish = (' FIN ' + str(self.current_seq) + '~').encode()
        h.update(finish)
        finish = h.hexdigest().encode() + finish
        #print("Sent: %s at %s" % (finish, self.millis()))
        self.socket.sendto(finish, (self.dst_ip, self.dst_port))

    def send_FINACK(self) -> None:
        h = hashlib.md5()
        finishack = (' FINACK ' + str(self.current_seq) + '~').encode()
        h.update(finishack)
        finishack = h.hexdigest().encode() + finishack
        #print("Sent: %s at %s" % (finishack, self.millis()))
        self.socket.sendto(finishack, (self.dst_ip, self.dst_port))

    def recv(self) -> bytes:

        while self.sending:
            sleep(0.01)

        self.receiving = True

        while True:
            if self.current_seq in self.buffer:
                data = self.buffer.pop(self.current_seq)
                self.last_ACK = self.current_seq - 1
                self.current_seq += 1
                break

        #print("Retrieved: %s at %s" % (data, self.millis()))

        self.receiving = False

        return data

    def listen(self) -> None:
        while self.listening:

            try:
                totpacket, addr = self.socket.recvfrom()

            except Exception as e:
                print("Listener died: " + str(e))

            else:
                #print("Got: %s at %s" % (totpacket, self.millis()))
                h = hashlib.md5()

                hash, packet = totpacket.split(b' ', 1)
                h.update(b' ' + packet)
                broke = False

                try:
                    if hash.decode() != h.hexdigest():
                        broke = True
                except Exception as e:
                    continue
                else:
                    if not broke:
                        header, data = packet.split(b'~')
                        packet_type, seq_num = header.split(b' ')
                        seq_num = int(seq_num)

                        if packet_type == b'DAT':
                            self.wait_to_send += 1

                            if seq_num == self.last_ACK + 1:
                                self.buffer[seq_num] = data
                                self.last_ACK += 1

                            elif seq_num > self.last_ACK + 1:
                                self.buffer[seq_num] = data

                            if self.wait_to_send >= DATS_B4_ACK:
                                self.send_ACK(self.last_ACK)
                                self.wait_to_send = 0

                        elif packet_type == b'ACK':

                            if seq_num > self.last_ACK:
                                self.last_ACK = seq_num

                            else:
                                pass

                        elif packet_type == b'FIN':
                            self.FIN = True

                        elif packet_type == b'FINACK':
                            self.FIN = True
                            self.FINACK = True

    def stop_listening(self) -> None:
        self.listening = False
        self.socket.stoprecv()

    def close(self) -> None:

        while self.sending or self.receiving:
            sleep(0.01)

        self.send_FIN()
        miliseconds = 0
        while not self.FIN:
            if (miliseconds % 50) == 49:
                self.send_FIN()
            sleep(0.01)
            miliseconds += 1

        self.send_FINACK()
        miliseconds = 0
        while not self.FINACK:
            if (miliseconds % 50) == 49:
                self.send_FINACK()
            if miliseconds >= 250:
                 break
            sleep(0.01)
            miliseconds += 1

        self.timing = False
        sleep(1)

        self.stop_listening()

        self.data_to_send = {} # Buffer to send items
        self.buffer = {} # Buffer for recieved items

        self.listening = True
        self.FIN = False
        self.FINACK = False

        self.sending = False
        self.receiving = False

        self.current_seq = -1 # The current packetnum to be sent and to be expected
        self.last_ACK = -1 # The last packetnum that was acked
        self.sender_index = 0 # For labeling the packets to be sent

    def parse_packet(self, packet: bytes) -> None:
        pass

    def checksum(self, string: bytes) -> str:
        pass

    def wait_for_ACK(self,  packet_num: int) -> None:

        miliseconds = 0
        timeout = 25
        while (self.last_ACK < self.current_seq and miliseconds < timeout):
            sleep(0.01)
            miliseconds += 1

        if miliseconds >= timeout:
            self.resend(packet_num)


    def break_string(self, string: bytes, length: int) -> list:
        return(string[0+i:length+i] for i in range(0, len(string), length))

    def millis(self):
        return int(round(time.time() * 1000))


if __name__ == '__main__':
    s = Streamer(dst_ip="localhost", dst_port=8000,
                 src_ip="localhost", src_port=8001)
    sleep(1)
    s.close()
