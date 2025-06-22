import socket
import threading
import base64
import json
import os
import pyaudio
import wave
import time
from getpass import getpass
from playsound import playsound
from PIL import Image, ImageGrab
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

def derive_key(password: str, salt: bytes) -> bytes:
    """Derives a key from a password and salt."""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    return base64.urlsafe_b64encode(kdf.derive(password.encode()))

# --- Networking and Logic ---
class VoiceCallManager:
    def __init__(self, f_obj, peer_ip, peer_port, my_socket):
        self.f_obj = f_obj
        self.peer_ip = peer_ip
        self.peer_port = peer_port
        self.receive_socket = my_socket
        self.my_port = my_socket.getsockname()[1]
        self.is_running = False
        self.p_audio = pyaudio.PyAudio()
        self.CHUNK = 1024
        self.FORMAT = pyaudio.paInt16
        self.CHANNELS = 1
        self.RATE = 22050  # Lower rate for less bandwidth
        self.send_socket = None
        self.stream = None

    def start(self):
        self.is_running = True
        
        self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # The receive_socket is now passed in, already bound.

        self.stream = self.p_audio.open(format=self.FORMAT,
                                        channels=self.CHANNELS,
                                        rate=self.RATE,
                                        input=True,
                                        output=True,
                                        frames_per_buffer=self.CHUNK)

        threading.Thread(target=self.receive_thread, daemon=True).start()
        threading.Thread(target=self.send_thread, daemon=True).start()

    def stop(self):
        self.is_running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        if self.send_socket:
            self.send_socket.close()

    def send_thread(self):
        while self.is_running:
            try:
                data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                encrypted_data = self.f_obj.encrypt(data)
                self.send_socket.sendto(encrypted_data, (self.peer_ip, self.peer_port))
            except Exception:
                break

    def receive_thread(self):
        while self.is_running:
            try:
                data, addr = self.receive_socket.recvfrom(self.CHUNK + 512)
                decrypted_data = self.f_obj.decrypt(data)
                self.stream.write(decrypted_data)
            except Exception:
                if self.is_running:
                    continue
                break

class ChatClient:
    def __init__(self, key, **kwargs):
        self.f_obj = Fernet(key)
        self.sock = None
        self.is_connected = False
        self.pending_conn = None
        self.connection_event = threading.Event()
        self.connection_accepted = False
        self.voice_call_manager = None
        self.my_pending_udp_socket = None
        self.send_lock = threading.Lock()
        
        self.on_message_received = kwargs.get('on_message_received')
        self.on_connection_status = kwargs.get('on_connection_status')
        self.on_image_received = kwargs.get('on_image_received')
        self.on_audio_received = kwargs.get('on_audio_received')
        self.on_connection_request = kwargs.get('on_connection_request')
        self.on_call_request = kwargs.get('on_call_request')
        self.on_call_status = kwargs.get('on_call_status')
        
        self.downloads_dir = "downloads"
        if not os.path.exists(self.downloads_dir):
            os.makedirs(self.downloads_dir)

    def send_data(self, data: bytes):
        """Encrypts and sends data with a 4-byte length prefix under a lock."""
        with self.send_lock:
            encrypted_data = self.f_obj.encrypt(data)
            self.sock.sendall(len(encrypted_data).to_bytes(4, 'big') + encrypted_data)

    def encrypt(self, data: bytes) -> bytes:
        return self.f_obj.encrypt(data)

    def decrypt(self, encrypted_data: bytes) -> bytes:
        return self.f_obj.decrypt(encrypted_data)

    def listen(self, host, port):
        """Listens for an incoming connection."""
        listen_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_socket.bind((host, port))
        listen_socket.listen(1)
        if self.on_connection_status:
            self.on_connection_status(f"Listening on {host}:{port}...", is_connected=False)
        
        # Loop to allow for multiple connection attempts (e.g., after a rejection)
        while not self.is_connected:
            try:
                conn, addr = listen_socket.accept()
            except OSError:
                return # Socket has been closed, exit thread

            self.pending_conn = conn
            self.connection_event.clear()
            self.connection_accepted = False

            if self.on_connection_request:
                self.on_connection_request(addr)
            else:
                # If no UI handler, just accept automatically
                self.connection_accepted = True
            
            # Wait for the UI to signal accept or reject
            self.connection_event.wait()

            if self.connection_accepted:
                self.sock = self.pending_conn
                self.is_connected = True
                if self.on_connection_status:
                    self.on_connection_status(f"Connected by {addr[0]}:{addr[1]}", is_connected=True)
                
                # Start the receive loop in a new thread
                threading.Thread(target=self.receive_loop, daemon=True).start()
                break # Exit the listening loop
            else:
                # Connection was rejected, close the socket and listen for the next one
                self.pending_conn.close()
                self.pending_conn = None
                if self.on_connection_status:
                    self.on_connection_status(f"Connection rejected. Listening again...", is_connected=False)
        
        listen_socket.close()

    def confirm_connection(self):
        """Called by the UI to confirm a pending connection."""
        self.connection_accepted = True
        self.connection_event.set()

    def reject_connection(self):
        """Called by the UI to reject a pending connection."""
        self.connection_accepted = False
        self.connection_event.set()

    def connect(self, host, port):
        """Connects to a listening peer."""
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.sock.connect((host, port))
            self.is_connected = True
            if self.on_connection_status:
                self.on_connection_status(f"Connected to {host}:{port}", is_connected=True)
            threading.Thread(target=self.receive_loop, daemon=True).start()
        except Exception as e:
            self.is_connected = False
            if self.on_connection_status:
                self.on_connection_status(f"Connection failed: {e}", is_connected=False)

    def receive_loop(self):
        """Handles receiving messages and files."""
        while self.is_connected:
            try:
                # First, receive the size of the incoming message
                size_data = self.sock.recv(4)
                if not size_data:
                    self.handle_disconnect()
                    break
                
                msg_size = int.from_bytes(size_data, 'big')
                
                # Now receive the actual message
                data = b""
                while len(data) < msg_size:
                    packet = self.sock.recv(msg_size - len(data))
                    if not packet:
                        self.handle_disconnect()
                        return
                    data += packet

                decrypted_data = self.decrypt(data)
                message = json.loads(decrypted_data.decode('utf-8'))
                msg_type = message['type']
                payload = message['payload']

                if msg_type == 'text':
                    if self.on_message_received:
                        self.on_message_received(payload, "Peer")
                
                elif msg_type == 'disconnect':
                    self.handle_disconnect()
                    break

                elif msg_type in ['file', 'image', 'audio']:
                    filename = payload['name']
                    filepath = os.path.join(self.downloads_dir, os.path.basename(filename))
                    file_data = base64.b64decode(payload['data'])

                    with open(filepath, 'wb') as f:
                        f.write(file_data)
                    
                    # Trigger callbacks for UI
                    if msg_type == 'image':
                        if self.on_image_received: self.on_image_received(filepath, "Peer")
                    elif msg_type == 'audio':
                        duration = payload.get('duration', 0)
                        if self.on_audio_received: self.on_audio_received(filepath, duration, "Peer")
                    else: # Generic file
                        if self.on_message_received:
                            self.on_message_received(f"File '{filename}' received and saved to '{self.downloads_dir}'.")

                # --- Call Signaling ---
                elif msg_type == 'call_request':
                    if self.on_call_request:
                        self.on_call_request(payload)
                elif msg_type == 'call_accepted':
                    if self.on_call_status: self.on_call_status("Call connected. Starting stream...")
                    if self.my_pending_udp_socket:
                        peer_udp_port = payload['udp_port']
                        self.start_voice_call(peer_udp_port, self.my_pending_udp_socket)
                        self.my_pending_udp_socket = None # Clear after use
                    else:
                        print("ERROR: Received 'call_accepted' but no pending call was initiated.")
                elif msg_type == 'call_rejected':
                    if self.on_call_status: self.on_call_status("Call rejected by peer.")
                    self.stop_voice_call() # Cleans up pending socket
                elif msg_type == 'call_end':
                    if self.on_call_status: self.on_call_status("Call ended by peer.")
                    self.stop_voice_call()

            except (ConnectionResetError, BrokenPipeError):
                self.handle_disconnect()
                break
            except (json.JSONDecodeError, ValueError) as e:
                print(f"Data corruption or format error: {e}")
                # Don't disconnect for a single bad message, but log it.
                continue
            except Exception as e:
                import traceback
                print(f"UNEXPECTED ERROR in receive_loop:")
                traceback.print_exc()
                self.handle_disconnect()
                break
    
    def send_message(self, message):
        if self.is_connected and message:
            try:
                msg_json = json.dumps({'type': 'text', 'payload': message})
                self.send_data(msg_json.encode('utf-8'))
            except (ConnectionResetError, BrokenPipeError):
                self.handle_disconnect()
    
    def send_file(self, filepath, is_audio=False, duration=None):
        if not self.is_connected or not os.path.exists(filepath):
            return
        
        try:
            filename = os.path.basename(filepath)
            with open(filepath, 'rb') as f:
                file_data = f.read()
            
            file_data_b64 = base64.b64encode(file_data).decode('utf-8')

            payload = {
                'name': filename,
                'data': file_data_b64
            }
            
            msg_type = 'file'
            if is_audio:
                msg_type = 'audio'
                payload['duration'] = duration
            elif self.is_image(filepath):
                msg_type = 'image'

            info_json = json.dumps({'type': msg_type, 'payload': payload})
            self.send_data(info_json.encode('utf-8'))
            
            # Trigger UI update for the sender
            if msg_type == 'image':
                if self.on_image_received: self.on_image_received(filepath, "You")
            elif msg_type == 'audio':
                if self.on_audio_received: self.on_audio_received(filepath, duration, "You")
            else:
                if self.on_message_received:
                    self.on_message_received(f"You sent file: {filename}")

        except (ConnectionResetError, BrokenPipeError):
            self.handle_disconnect()
        except Exception as e:
             if self.on_message_received:
                self.on_message_received(f"System: Failed to send file: {e}")

    def is_image(self, filepath):
        """Checks if a file is an image based on extension."""
        return filepath.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))

    def is_audio(self, filepath):
        """Checks if a file is an audio file based on extension."""
        return filepath.lower().endswith('.wav')

    def handle_disconnect(self):
        if not self.is_connected:
            return
            
        self.is_connected = False
        
        if self.on_message_received:
            self.on_message_received("Peer has left the chat.", "System")

        if self.on_connection_status:
            self.on_connection_status("Connection lost.", is_connected=False)
            
        self.stop_voice_call() # Ensure call resources are cleaned up
        if self.sock:
            self.sock.close()
            self.sock = None

    def disconnect(self):
        """Public method to disconnect the client."""
        if self.is_connected:
            try:
                msg = {"type": "disconnect", "payload": ""}
                json_msg = json.dumps(msg).encode('utf-8')
                self.send_data(json_msg)
            except Exception as e:
                print(f"Could not send disconnect message: {e}")

        self.handle_disconnect()

    def send_call_request(self):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(('0.0.0.0', 0))
            self.my_pending_udp_socket = s
            my_udp_port = s.getsockname()[1]
            
            msg = {"type": "call_request", "payload": {"udp_port": my_udp_port}}
            self.send_data(json.dumps(msg).encode('utf-8'))
            if self.on_call_status: self.on_call_status("Ringing...")
            return True
        except Exception as e:
            if self.on_call_status: self.on_call_status(f"Call failed: {e}")
            self.stop_voice_call()
            return False

    def accept_call(self, peer_udp_port):
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.bind(('0.0.0.0', 0))
            my_udp_port = s.getsockname()[1]

            msg = {"type": "call_accepted", "payload": {"udp_port": my_udp_port}}
            self.send_data(json.dumps(msg).encode('utf-8'))
            self.start_voice_call(peer_udp_port, s)
            return True
        except Exception as e:
            if self.on_call_status: self.on_call_status(f"Accept failed: {e}")
            return False

    def reject_call(self):
        msg = {"type": "call_rejected", "payload": ""}
        self.send_data(json.dumps(msg).encode('utf-8'))
        self.stop_voice_call()
        if self.on_call_status: self.on_call_status("Call ended.")
    
    def start_voice_call(self, peer_udp_port, my_socket):
        if self.voice_call_manager: return
        peer_ip = self.sock.getpeername()[0]
        self.voice_call_manager = VoiceCallManager(self.f_obj, peer_ip, peer_udp_port, my_socket)
        self.voice_call_manager.start()

    def stop_voice_call(self):
        if self.voice_call_manager:
            self.voice_call_manager.stop()
            self.voice_call_manager = None
        if self.my_pending_udp_socket:
            self.my_pending_udp_socket.close()
            self.my_pending_udp_socket = None

# --- Voice Recorder ---
class VoiceRecorder:
    def __init__(self):
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.start_time = 0

    def start_recording(self):
        if self.is_recording:
            return
        self.is_recording = True
        self.frames = []
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=44100,
                                  input=True,
                                  frames_per_buffer=1024)
        self.start_time = time.time()
        threading.Thread(target=self._record_loop, daemon=True).start()

    def _record_loop(self):
        while self.is_recording:
            try:
                data = self.stream.read(1024)
                self.frames.append(data)
            except IOError: # Stream closed
                break
    
    def stop_recording(self) -> (str, float):
        if not self.is_recording:
            return None, 0
        self.is_recording = False
        duration = time.time() - self.start_time
        
        self.stream.stop_stream()
        self.stream.close()
        
        filepath = f"voice_message_{int(time.time())}.wav"
        with wave.open(filepath, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(self.p.get_sample_size(pyaudio.paInt16))
            wf.setframerate(44100)
            wf.writeframes(b''.join(self.frames))
            
        return filepath, duration

    def terminate(self):
        self.p.terminate()