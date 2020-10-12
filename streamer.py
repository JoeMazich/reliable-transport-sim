# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from concurrent import futures

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
        self.buffer = {}
        self.closed = False

        executor = futures.ThreadPoolExecutor(max_workers=1)
        executor.submit(self.listener)

    def listener(self) -> None:
        # While listening
        print('Starting listener')
        while not self.closed:
            # Try to get packets and add them to the buffer
            try:
                packet, addr = self.socket.recvfrom()
            # Print out if something goes wrong
            except Exception as e:
                print("Listener died: " + str(e))
            else:
                header, data = packet.split(b' ', 1)
                # This is where we can decode the header accoriding to how we set it in the sending method above
                # This buffer is made for re-orderign the data (value) given its sequence numbers (keys) as a dict
                self.buffer[int(header.decode())] = data

        print("Listener closing...")

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        # Your code goes here!  The code below should be changed!

        # Set some max values for things (in bytes)
        max_header_length = 11
        max_packet_length = 1472
        data_length = max_packet_length - max_header_length
        # Rename data_bytes for easy of use (easier to read)
        remaining_bytes = data_bytes
        # Append the data_to_send list with the...you guessed it, data to send (if the data is larger than one packet)
        while len(remaining_bytes) > data_length:
            # But also, make each entry the proper length
            self.data_to_send.append(remaining_bytes[0:data_length])
            # Find how many remaining bytes you have
            remaining_bytes = remaining_bytes[data_length:]
        # Append the last of the bytes that didnt make the cut
        self.data_to_send.append(remaining_bytes)
        # Sending the data
        for data in self.data_to_send:
            # Create the header, this is where we can add more info about the packet
            # (BE MINDFUL OF ITS SIZE AND ADJUST max_header_length ACCORDINGLY)
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

        # Constantly check to see if the seq num is in the buffer
        while True:
            # (sidenote: this is where we can use timeout)
            if self.currentIndex in self.buffer:
                # If it is, pop it out, get the next seq num, and break
                full_data = self.buffer.pop(self.currentIndex)
                self.currentIndex += 1
                break

        return full_data

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.

        # Reset the index for sequencing
        self.currentIndex = 0
        # Redundency for setting the data to send to be clear
        self.data_to_send.clear()
        # Close the listener
        self.closed = True
        self.socket.stoprecv()
        pass
