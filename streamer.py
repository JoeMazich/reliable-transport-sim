# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY

class Streamer:
    def __init__(self, dst_ip, dst_port,
                 src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
           and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.currentIndex = 0
        self.data_to_send = []
        self.remainder = ""

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!
        remaining_bytes = data_bytes
        while len(remaining_bytes) > 1472:
            sending_bytes = remaining_bytes[0:1472]
            remaining_bytes = remaining_bytes[1472:]
            self.socket.sendto(sending_bytes, (self.dst_ip, self.dst_port))
        self.socket.sendto(remaining_bytes, (self.dst_ip, self.dst_port))

        # for now I'm just sending the raw application-level data in one UDP payload
        #self.socket.sendto(data_bytes, (self.dst_ip, self.dst_port))

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        for data in self.data_to_send:
            if int(data) == self.currentIndex:
                self.currentIndex += 1
                return data.encode('utf-8')

        return_data = None
        while True:
            data, addr = self.socket.recvfrom()
            data_bytes = (self.remainder + data.decode('utf-8')).split()
            if data.decode('utf-8')[-1:] != ' ':
                self.remainder = data_bytes.pop()
            else:
                self.remainder = ""
            #print("DATA: ", data_bytes)
            for data_byte in data_bytes:
                #print("DATA_BYTE: ", data_byte)
                if int(data_byte) == self.currentIndex:
                    return_data = data_byte
                else:
                    self.data_to_send.append(data_byte)
            if return_data:
                self.currentIndex += 1
                return return_data.encode('utf-8')

        # this sample code just calls the recvfrom method on the LossySocket
        #data, addr = self.socket.recvfrom()
        # For now, I'll just pass the full UDP payload to the app
        #return data

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        pass
