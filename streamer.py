# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from concurrent import futures
from time import sleep
import time
import hashlib

class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        self.current_seq = -1 # The current packetnum to be sent and to be expected
        self.last_ACK = -1 # The last packetnum that was acked
        self.sender_index = 0 # For labeling the packets to be sent

        self.data_to_send = {} # Buffer to send items
        self.buffer = {} # Buffer for recieved items

        self.listening = True
        self.FIN = False
        self.FINACK = False

        self.sending = False
        self.receiving = False

        executor = futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listen)

    def send(self, data_bytes: bytes) -> None:

        while self.receiving:
            sleep(0.01)

        self.sending = True

        header_length = 10
        max_packet_length = 1210 #idk how long the hash is so I'm just going to low ball it

        data_length = max_packet_length - header_length

        total_to_send = 0
        self.sender_index = self.current_seq + 1
        for data in self.break_string(data_bytes, data_length):
            self.data_to_send[self.sender_index] = data
            self.sender_index += 1
            total_to_send += 1

        for _ in range(total_to_send):

            self.current_seq += 1

            data = self.data_to_send[self.current_seq]
            h = hashlib.md5()
            h.update(str(self.current_seq).encode())
            h.update(b" ")
            h.update(data)

            header = ('DAT ' + str(self.current_seq) + ' ' + h.hexdigest() + '~').encode()
            packet = header + data

            print("Sent: %s at %s" % (packet, self.millis()))

            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
            self.wait_for_ACK(self.current_seq)

        self.sending = False

    def resend(self, packet_num: int) -> None:
        data = self.data_to_send[packet_num]
        h = hashlib.md5()
        h.update(str(self.current_seq).encode())
        h.update(b" ")
        h.update(data)

        header = ('DAT ' + str(packet_num) + ' ' + h.hexdigest() + '~').encode()

        packet = header + data

        print("Resent: %s at %s" % (packet, self.millis()))

        self.socket.sendto(packet, (self.dst_ip, self.dst_port))

        self.wait_for_ACK(packet_num)

    def send_ACK(self) -> None:
        #print("SENDING ACK1")
        h = hashlib.md5()
        #print("SENDING ACK2")
        h.update(str(self.current_seq).encode())
        #print("SENDING ACK3")
        acknowledgement = ('ACK ' + str(self.current_seq) + ' ' + h.hexdigest() + '~').encode()
        print("Sent: %s at %s" % (acknowledgement, self.millis()))
        self.socket.sendto(acknowledgement, (self.dst_ip, self.dst_port))

    def send_FIN(self) -> None:
        h = hashlib.md5()
        h.update(str(self.current_seq).encode())

        finish = ('FIN ' + str(self.current_seq) + ' ' + h.hexdigest() + '~').encode()
        print("Sent: %s at %s" % (finish, self.millis()))
        self.socket.sendto(finish, (self.dst_ip, self.dst_port))

    def send_FINACK(self) -> None:
        h = hashlib.md5()
        h.update(str(self.current_seq).encode())

        finack = ('FINACK ' + str(self.current_seq) + ' ' + h.hexdigest() + '~').encode()
        print("Sent: %s at %s" % (finack, self.millis()))
        self.socket.sendto(finack, (self.dst_ip, self.dst_port))


    def recv(self) -> bytes:

        while self.sending:
            sleep(0.01)

        self.receiving = True
        got_data = False

        while True:
            buffer = self.buffer.copy()

            for seq_num in buffer:
                if int(seq_num) < self.current_seq + 1:
                    del self.buffer[seq_num]
                elif int(seq_num) == self.current_seq + 1:
                    #("BUFFER: ", buffer)
                    data = self.buffer.pop(self.current_seq + 1)
                    self.current_seq += 1
                    got_data = True

            if got_data:
                break

        print("Retrieved: %s at %s" % (data, self.millis()))

        self.receiving = False

        return data

    def listen(self) -> None:

        while self.listening:
            #print("STILL LISTENING")
            try:
                packet, addr = self.socket.recvfrom()

            except Exception as e:
                print("Listener died: " + str(e))

            else:
                print("Got: %s at %s" % (packet, self.millis()))
                packet_parts = packet.split(b'~', 1)
                if len(packet_parts) != 2: #Corruption deleted the ~ char
                    continue
                header, data = packet_parts[0], packet_parts[1]

                try:
                    header = header.decode() #Corruption caused decoding to throw a syntax error

                except Exception:
                    #print("SYNTAX ERROR OCCURED")
                    continue

                else:
                    header_parts = header.split()
                    if len(header_parts) != 3: #Corruption added an extra space
                        continue
                    packet_type, seq_num, hash_value = header_parts[0], header_parts[1], header_parts[2]

                    try:
                        seq_num = int(seq_num)

                    except Exception: #Corruption caused chars to no longer be all numerical
                        continue

                    else:
                        h = hashlib.md5()

                        if packet_type == 'DAT':
                            h.update(str(seq_num).encode())
                            h.update(b" ")
                            h.update(data)
                            #print("DIGEST: ", h.hexdigest())
                            #print("HASH: ", hash_value)
                            if h.hexdigest() == hash_value:
                                #print("HASH TEST SUCCESS")
                                self.send_ACK()
                                #print("DATA PUT IN BUFFER: ", data)
                                self.buffer[int(seq_num)] = data
                        elif packet_type == 'ACK':
                            h.update(str(seq_num).encode())
                            #print("DIGEST: ", h.hexdigest())
                            #print("HASH: ", hash_value)
                            if h.hexdigest() == hash_value:
                                if self.last_ACK < seq_num:
                                    self.last_ACK = seq_num
                        elif packet_type == 'FIN':
                            h.update(str(seq_num).encode())
                            #print("DIGEST: ", h.hexdigest())
                            #print("HASH: ", hash_value)
                            if h.hexdigest() == hash_value:
                                self.FIN = True
                        elif packet_type == 'FINACK':
                            h.update(str(seq_num).encode())
                            #print("DIGEST: ", h.hexdigest())
                            #print("HASH: ", hash_value)
                            if h.hexdigest() == hash_value:
                                self.FIN = True
                                self.FINACK = True
                        #else:
                            #print("CORRUPTION OCCURED BUT THAT'S OKAY")

    def stop_listening(self) -> None:
        self.listening = False
        self.socket.stoprecv()

    def close(self) -> None:

        sleep(1)

        self.send_FIN()
        miliseconds = 0
        while not self.FIN:
            if (miliseconds % 50) == 49:
                self.send_FIN()
            sleep(0.01)
            miliseconds += 1

        #self.send_FINACK()
        #miliseconds = 0
        #while not self.FINACK:
            #if (miliseconds % 50) == 49:
                #self.send_FINACK()
            #if miliseconds >= 500:
                #break
            #sleep(0.01)
            #miliseconds += 1


        sleep(1)

        self.stop_listening()

        sleep(10)

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

        sleep(5)


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
