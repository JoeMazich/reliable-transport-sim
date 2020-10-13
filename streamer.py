# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP
# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY
from concurrent import futures
from time import sleep

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
        self.ACK = False
        self.FIN = False

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
                # Split off the header from the body
                header, data = packet.split(b'~', 1)

                # This is where we can decode the header accoriding to how we set it in the sending method
                header = header.decode()
                packet_type, seq_num = header.split(' ')

                # Look at what tpye of packet it is and do things accordingly
                if packet_type == 'DAT':
                    # If it is a DATa pack
                    # Send an ACK that we got the packet
                    acknowledgement = ('ACK ' + str(self.currentIndex) + '~').encode()
                    self.socket.sendto(acknowledgement, (self.dst_ip, self.dst_port))
                    # Check to see if we should save the data (we didn't get the packet before) or not (we got it before and this is a dup)
                    if int(seq_num) >= self.currentIndex:
                        self.buffer[int(seq_num)] = data

                elif packet_type == 'ACK':
                    # If it is an ACKnlodgement pack
                    # Check the ACK number, if it is bigger than or equal to the one we are waiting on...
                    if self.currentIndex <= int(seq_num):
                        # We are no longer waiting and we are good to send more packets
                        self.ACK = True

                elif packet_type == 'FIN':
                    self.FIN = True

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
            header = ('DAT ' + str(self.currentIndex) + '~').encode()
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

        # Wait for acknowledgement - gotta pass through the sending bytes just in case of timeout
        # could fix that by defining another function other than send that actually sends the data
        # but then you gotta be more carefult about the data_to_send and the function names will be really confusing
        self.wait_for_ACK(data_bytes)


    def wait_for_ACK(self, data_bytes: bytes) -> None:
        seconds = 0.
        # Wait for an ACK - it is found by the listener and stops there
        # Thats why it looks like nothing is happening here
        while (not self.ACK and seconds <= 0.25):
            sleep(0.01)
            seconds += 0.01
        if seconds > 0.25:
            self.currentIndex -= 1
            self.send(data_bytes)
        else:
            self.ACK = False


    def recv(self) -> bytes:
        """Blocks (waits) if no data is ready to be read from the connection."""
        # your code goes here!  The code below should be changed!

        # Constantly check to see if the seq num is in the buffer
        while True:
            if self.currentIndex in self.buffer:
                # If it is, pop it out, get the next seq num, and break
                full_data = self.buffer.pop(self.currentIndex)
                self.currentIndex += 1
                break

        temp = {key:val for key, val in self.buffer.items() if key >= self.currentIndex}
        self.buffer = temp
        # Send an ACK that we got the next packet
        # right now, they are technically sending in order, so...
        # Later on, might be good idea to send the ack number instead of just 0
        acknowledgement = ('ACK ' + str(self.currentIndex) + '~').encode()
        self.socket.sendto(acknowledgement, (self.dst_ip, self.dst_port))
        return full_data

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
           the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.

        finish = ('FIN ' + str(self.currentIndex) + '~').encode()
        self.socket.sendto(finish, (self.dst_ip, self.dst_port))

        while not self.FIN:
            sleep(0.01)
        print('Finished stream')
        # Reset the index for sequencing
        self.currentIndex = 0
        # Close the listener, some of this might be transfered to the listener function itself later
        self.closed = True
        self.socket.stoprecv()
        # Set Fin back to false just incase you want to use the same stream later
        self.FIN = False

        # Redundency for setting the data to send to be clear
        self.data_to_send.clear()
        # Ensure that self.ACK is False for next connection
        self.ACK = False
        pass
