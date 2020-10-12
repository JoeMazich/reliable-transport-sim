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

        # Set some max values for things
        max_header_length = 11
        max_packet_length = 1472
        data_length = max_packet_length - max_header_length
        # Rename data_bytes for easy of use (easier to read)
        remaining_bytes = data_bytes
        # Append the data_to_send list with the...you guessed it, data to send
        while len(remaining_bytes) > data_length:
            # But also, make each entry the proper length
            self.data_to_send.append(remaining_bytes[0:data_length])
            # Find how many remaining bytes you have
            remaining_bytes = remaining_bytes[data_length:]
        # Append the last of the bytes that didnt make the cut
        self.data_to_send.append(remaining_bytes)
        # Sending the data
        for data in self.data_to_send:
            # Create the header
            header = (str(self.currentIndex) + ' ').encode()
            self.currentIndex += 1
            # Create the actual packet to send
            packet = header + data
            # Make sure everything is not TOO big (hopefully not too small either, want it to be juuust right)
            assert (len(header) <= max_header_length)
            assert (len(packet) <= max_packet_length)
            # Send the packet
            self.socket.sendto(packet, (self.dst_ip, self.dst_port))
        # Clear out the data_to_send list for later use - for when you send another packet
        # so you don't send the same packets again
        self.data_to_send.clear()

    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!
        '''for data in self.data_to_send:
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
                return return_data.encode('utf-8')'''

        # this sample code just calls the recvfrom method on the LossySocket
        packet, addr = self.socket.recvfrom()
        header, data = packet.split(b' ', 1)

        # For now, I'll just pass the full UDP payload to the app
        return data

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.

        # Reset the index for sequencing
        self.currentIndex = 0
        # Redundency for setting the data to send to be clear
        self.data_to_send.clear()
        pass
