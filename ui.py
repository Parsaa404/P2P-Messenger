import customtkinter as ctk
import tkinter as tk
import threading
from tkinter import filedialog, font
import os
import time
from PIL import Image, ImageGrab, ImageTk
from playsound import playsound

# Import logic from the other file
from p2p_messenger import ChatClient, derive_key, VoiceRecorder

class ChatApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("P2P Encrypted Messenger")
        self.geometry("400x500")
        self.chat_client = None
        self.recorder = VoiceRecorder()
        self.last_connection_details = {}

        # --- Font Handling ---
        self.initialize_fonts()

        self.setup_login_ui()
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.bind("<Control-V>", self.paste_from_clipboard)

    def initialize_fonts(self):
        """Load custom font and create a combined font for use."""
        font_path = os.path.join("fonts", "Vazirmatn-Regular.ttf")
        if os.path.exists(font_path):
            # This is a bit of a workaround for tkinter to recognize the font
            # It might not work on all systems without font installation
            try:
                # For Windows
                from ctypes import windll, byref, create_unicode_buffer
                FR_PRIVATE = 0x10
                windll.gdi32.AddFontResourceExW(font_path, FR_PRIVATE, 0)
            except (ImportError, OSError):
                print("Could not load font dynamically. Please install 'Vazirmatn-Regular.ttf' manually.")

            # Define a primary font and a fallback for Persian
            self.app_font = ("Segoe UI", 13)
            self.persian_font_family = "Vazirmatn Regular"
        else:
            print(f"Font not found at {font_path}. Using default fonts.")
            self.app_font = ("Segoe UI", 13)
            self.persian_font_family = "Arial" # A common fallback

    def setup_login_ui(self):
        self.clear_frame()
        self.login_frame = ctk.CTkFrame(self)
        self.login_frame.pack(pady=20, padx=20, fill="both", expand=True)

        ctk.CTkLabel(self.login_frame, text="P2P Messenger", font=("Arial", 24)).pack(pady=12)

        self.secret_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Shared Secret", show="*")
        self.secret_entry.pack(pady=12, padx=10)

        self.ip_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Peer IP (for connecting)")
        self.ip_entry.pack(pady=12, padx=10)

        self.port_entry = ctk.CTkEntry(self.login_frame, placeholder_text="Port")
        self.port_entry.pack(pady=12, padx=10)

        ctk.CTkButton(self.login_frame, text="Listen for Connection", command=self.start_listening).pack(pady=5)
        ctk.CTkButton(self.login_frame, text="Connect to Peer", command=self.start_connecting).pack(pady=5)

        self.status_label = ctk.CTkLabel(self.login_frame, text="", font=self.app_font)
        self.status_label.pack(pady=10)
        
        info_text = "For internet connection:\n'Listen' user must do Port Forwarding in their router.\n'Connect' user must use the Public IP of the listener."
        ctk.CTkLabel(self.login_frame, text=info_text, font=(self.app_font[0], 10), text_color="gray").pack(pady=10, side="bottom")

    def setup_chat_ui(self):
        self.clear_frame()
        
        self.chat_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.chat_frame.pack(pady=10, padx=10, fill="both", expand=True)
        self.chat_frame.grid_rowconfigure(0, weight=1)
        self.chat_frame.grid_columnconfigure(0, weight=1)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.chat_frame)
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", columnspan=2)
        self.scrollable_frame.columnconfigure(0, weight=1)

        bottom_frame = ctk.CTkFrame(self.chat_frame)
        bottom_frame.grid(row=1, column=0, sticky="ew", pady=(10,0))
        bottom_frame.columnconfigure(0, weight=1)

        self.message_entry = ctk.CTkEntry(bottom_frame, placeholder_text="Type your message...", font=(self.persian_font_family, 13))
        self.message_entry.grid(row=0, column=0, pady=5, padx=5, sticky="ew")
        self.message_entry.bind("<Return>", lambda event: self.send_chat_message())

        self.send_button = ctk.CTkButton(bottom_frame, text="Send", command=self.send_chat_message, width=60)
        self.send_button.grid(row=0, column=1, pady=5, padx=5)

        self.attach_button = ctk.CTkButton(bottom_frame, text="📎", command=self.attach_file, width=40)
        self.attach_button.grid(row=0, column=2, pady=5, padx=5)

        self.mic_button = ctk.CTkButton(bottom_frame, text="🎙️", width=40)
        self.mic_button.grid(row=0, column=3, pady=5, padx=5)
        self.mic_button.bind("<ButtonPress-1>", self.start_recording_ui)
        self.mic_button.bind("<ButtonRelease-1>", self.stop_recording_ui)

        self.call_button = ctk.CTkButton(bottom_frame, text="📞", width=40, command=self.initiate_call)
        self.call_button.grid(row=0, column=4, pady=5, padx=5)

        # --- Status and Leave Button ---
        status_frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", pady=(5,0), columnspan=5)
        status_frame.columnconfigure(0, weight=1)

        self.status_label_chat = ctk.CTkLabel(status_frame, text="Connected", height=10, font=(self.app_font[0], 11), text_color="gray")
        self.status_label_chat.grid(row=0, column=0, sticky="ew")

        self.leave_button = ctk.CTkButton(status_frame, text="Leave Chat", command=self.leave_chat, width=80, height=20, font=(self.app_font[0], 10))
        self.leave_button.grid(row=0, column=1, padx=5)
    
    def clear_frame(self):
        for widget in self.winfo_children():
            widget.destroy()

    def start_listening(self):
        if not self.initialize_client(): return
        self.last_connection_details["mode"] = "listen"
        port = int(self.port_entry.get())
        threading.Thread(target=self.chat_client.listen, args=('0.0.0.0', port), daemon=True).start()

    def start_connecting(self):
        if not self.initialize_client(): return
        self.last_connection_details["mode"] = "connect"
        ip = self.ip_entry.get()
        port = int(self.port_entry.get())
        threading.Thread(target=self.chat_client.connect, args=(ip, port), daemon=True).start()
    
    def initialize_client(self):
        secret = self.secret_entry.get()
        if not secret or not self.port_entry.get():
            self.status_label.configure(text="Secret and Port are required.")
            return False
        
        # Store details for potential reconnect
        self.last_connection_details = {
            'secret': secret,
            'port': int(self.port_entry.get()),
            'ip': self.ip_entry.get()
        }

        SALT = b'p2p_chat_salt_'
        key = derive_key(secret, SALT)
        self.chat_client = ChatClient(key, 
                                     on_message_received=self.on_message_received,
                                     on_connection_status=self.on_connection_status,
                                     on_image_received=self.on_image_received,
                                     on_audio_received=self.on_audio_received,
                                     on_connection_request=self.on_connection_request,
                                     on_call_request=self.on_call_request,
                                     on_call_status=self.on_call_status)
        self.after(100, self._scroll_to_bottom)
        return True

    def send_chat_message(self):
        msg = self.message_entry.get()
        if msg:
            # Check if message contains Persian characters
            font_to_use = self.app_font
            if any("\u0600" <= char <= "\u06FF" for char in msg):
                 font_to_use = (self.persian_font_family, 14)

            self.chat_client.send_message(msg)
            self.display_message(msg, sender="You", font=font_to_use)
            self.message_entry.delete(0, tk.END)

    def display_message(self, message, sender=None, font=None):
        if font is None:
            font_to_use = self.app_font
            if any("\u0600" <= char <= "\u06FF" for char in message):
                 font_to_use = (self.persian_font_family, 14)
            else:
                font_to_use = self.app_font
        else:
            font_to_use = font
        
        # Handle System messages
        if sender == "System":
            msg_label = ctk.CTkLabel(self.scrollable_frame, text=message, font=(self.app_font[0], 11), text_color="gray")
            msg_label.pack(pady=5, padx=10, anchor="center")
            self.after(100, self._scroll_to_bottom)
            return

        display_text = message
        if sender == "Peer":
            display_text = f"Peer: {message}"

        bubble_color = "#2b3033"  # Peer's message color
        text_color = "white"
        justify = "left"
        anchor = "w"
        if sender == "You":
            bubble_color = "#005c4b"  # Your message color
            justify = "right"
            anchor = "e"
        
        # Create a bubble frame
        bubble_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=bubble_color, corner_radius=10)
        
        msg_label = ctk.CTkLabel(bubble_frame, text=display_text, wraplength=250, justify=justify, font=font_to_use, text_color=text_color)
        msg_label.pack(pady=5, padx=10)
        
        bubble_frame.pack(pady=2, padx=10, anchor=anchor)
        
        self.after(100, self._scroll_to_bottom)
    
    def on_message_received(self, message, sender="Peer"):
        # This is called from a worker thread, so we use `after` to safely update the UI
        self.after(0, self._update_ui_for_message, message, sender)

    def _update_ui_for_message(self, message, sender):
        """Helper function to run display_message on the main thread."""
        # Check if the chat UI is still active before proceeding
        if not hasattr(self, 'scrollable_frame') or not self.scrollable_frame.winfo_exists():
            return

        font_to_use = self.app_font
        if any("\u0600" <= char <= "\u06FF" for char in message):
            font_to_use = (self.persian_font_family, 14)
        self.display_message(message, sender=sender, font=font_to_use)

    def on_image_received(self, filepath, sender):
        self.after(0, self.display_image, filepath, sender)

    def on_audio_received(self, filepath, duration, sender):
        self.after(0, self.display_audio_player, filepath, duration, sender)

    def display_image(self, filepath, sender):
        try:
            anchor = "e" if sender == "You" else "w"
            bubble_color = "#005c4b" if sender == "You" else "#2b3033"

            bubble_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=bubble_color, corner_radius=10)
            
            image = Image.open(filepath)
            max_size = (250, 250)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            
            ctk_image = ctk.CTkImage(light_image=image, dark_image=image, size=image.size)
            
            img_label = ctk.CTkLabel(bubble_frame, image=ctk_image, text="")
            img_label.pack(pady=5, padx=5)

            bubble_frame.pack(pady=5, padx=10, anchor=anchor)

            self.after(100, self._scroll_to_bottom)

        except Exception as e:
            self.display_message(f"[Error displaying image: {e}]", sender="System")

    def display_audio_player(self, filepath, duration, sender):
        anchor = "e" if sender == "You" else "w"
        bubble_color = "#005c4b" if sender == "You" else "#2b3033"

        bubble_frame = ctk.CTkFrame(self.scrollable_frame, fg_color=bubble_color, corner_radius=10)
        
        def play_audio():
            try:
                abs_path = os.path.abspath(filepath)
                threading.Thread(target=playsound, args=(abs_path,), daemon=True).start()
            except Exception as e:
                print(f"Error playing sound: {e}")

        play_button = ctk.CTkButton(bubble_frame, text=f"▶️ Play (~{duration:.1f}s)", command=play_audio)
        play_button.pack(side="left", padx=10, pady=5)

        bubble_frame.pack(pady=5, padx=10, anchor=anchor)
        self.after(100, self._scroll_to_bottom)

    def _scroll_to_bottom(self):
        # Check if the chat UI components still exist before trying to scroll
        if hasattr(self, 'scrollable_frame') and self.scrollable_frame.winfo_exists():
            self.scrollable_frame._parent_canvas.yview_moveto(1.0)

    def on_connection_status(self, status, is_connected):
        if is_connected:
            self.after(0, self.setup_chat_ui)
            # This lambda ensures the status label exists before we try to configure it.
            self.after(100, lambda: self.status_label_chat.configure(text=status) if hasattr(self, 'status_label_chat') else None)
        else:
            # Handle all non-connected states
            try:
                # If chat UI is active, update its status label
                self.status_label_chat.configure(text=status)
                
                # If connection is lost or failed, offer reconnect
                if "lost" in status.lower() or "failed" in status.lower():
                    self.message_entry.configure(state="disabled")
                    self.send_button.configure(state="disabled")
                    self.attach_button.configure(state="disabled")
                    self.mic_button.configure(state="disabled")
                    self.call_button.configure(state="disabled")
                    self.leave_button.configure(text="Reconnect", command=self.attempt_reconnect)
            except (AttributeError, tk.TclError):
                # Otherwise, we must be on the login screen
                self.status_label.configure(text=status)

    def attempt_reconnect(self):
        """Tries to reconnect using the last known connection details."""
        if not self.last_connection_details:
            self.leave_chat() # No details to use, go to login
            return

        self.status_label_chat.configure(text="Attempting to reconnect...")
        
        # Re-initialize client with the same secret
        SALT = b'p2p_chat_salt_'
        key = derive_key(self.last_connection_details['secret'], SALT)
        self.chat_client = ChatClient(key, 
                                     on_message_received=self.on_message_received,
                                     on_connection_status=self.on_connection_status,
                                     on_image_received=self.on_image_received,
                                     on_audio_received=self.on_audio_received)
        
        mode = self.last_connection_details.get("mode")
        if mode == "listen":
            port = self.last_connection_details['port']
            threading.Thread(target=self.chat_client.listen, args=('0.0.0.0', port), daemon=True).start()
        elif mode == "connect":
            ip = self.last_connection_details['ip']
            port = self.last_connection_details['port']
            threading.Thread(target=self.chat_client.connect, args=(ip, port), daemon=True).start()

    def attach_file(self):
        filepath = filedialog.askopenfilename()
        if filepath:
            threading.Thread(target=self.chat_client.send_file, args=(filepath,), daemon=True).start()

    def paste_from_clipboard(self, event=None):
        if not self.chat_client or not self.chat_client.is_connected:
            return

        try:
            image = ImageGrab.grabclipboard()
            if isinstance(image, Image.Image):
                temp_filepath = f"pasted_image_{int(time.time())}.png"
                save_path = os.path.join(self.chat_client.downloads_dir, temp_filepath)
                image.save(save_path, 'PNG')

                threading.Thread(
                    target=self.chat_client.send_file,
                    args=(save_path,),
                    daemon=True
                ).start()
                
                return "break"
        except Exception:
            pass

    def start_recording_ui(self, event):
        self.mic_button.configure(text="Recording...")
        self.recorder.start_recording()

    def stop_recording_ui(self, event):
        self.mic_button.configure(text="🎙️")
        temp_filepath, duration = self.recorder.stop_recording()
        if temp_filepath:
            permanent_filepath = os.path.join(self.chat_client.downloads_dir, os.path.basename(temp_filepath))
            try:
                os.rename(temp_filepath, permanent_filepath)
                threading.Thread(
                    target=self.chat_client.send_file, 
                    args=(permanent_filepath, True, duration), 
                    daemon=True
                ).start()
            except OSError as e:
                print(f"Error moving/sending audio file: {e}")
    
    def leave_chat(self):
        """Disconnects from the chat and returns to the login screen."""
        if self.chat_client:
            self.chat_client.disconnect()
        self.setup_login_ui()

    def on_closing(self):
        if self.recorder:
            self.recorder.terminate()
        if self.chat_client:
            self.chat_client.disconnect()
        self.destroy()

    def on_connection_request(self, addr):
        """Callback for when a peer requests to connect."""
        self.after(0, self.show_connection_dialog, addr)

    def show_connection_dialog(self, addr):
        """Displays a modal dialog asking to accept/reject a connection."""
        dialog = ctk.CTkToplevel(self)
        dialog.title("Connection Request")
        dialog.geometry("300x150")
        dialog.transient(self) # Keep on top of main window
        dialog.grab_set()      # Modal
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.handle_connection_response(False, dialog)) # Handle closing the dialog

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(dialog)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure((0, 1), weight=1)

        label = ctk.CTkLabel(main_frame, text=f"Incoming connection from:\n{addr[0]}", font=self.app_font)
        label.grid(row=0, column=0, columnspan=2, pady=10)

        accept_button = ctk.CTkButton(main_frame, text="Accept", command=lambda: self.handle_connection_response(True, dialog))
        accept_button.grid(row=1, column=0, padx=10, pady=10)
        
        reject_button = ctk.CTkButton(main_frame, text="Reject", command=lambda: self.handle_connection_response(False, dialog), fg_color="#D32F2F", hover_color="#B71C1C")
        reject_button.grid(row=1, column=1, padx=10, pady=10)

        dialog.wait_window()

    def handle_connection_response(self, accepted, dialog):
        """Handles the user's response from the connection dialog."""
        dialog.destroy()
        if accepted:
            self.chat_client.confirm_connection()
        else:
            self.chat_client.reject_connection()

    def initiate_call(self):
        # The logic now correctly finds an available port on its own.
        if self.chat_client.send_call_request():
            self.show_call_window(is_caller=True)

    def on_call_request(self, payload):
        self.after(0, self.show_incoming_call_dialog, payload)

    def on_call_status(self, status):
        # This can be called to update the call window UI
        if hasattr(self, 'call_window') and self.call_window.winfo_exists():
            self.after(0, self.call_window.update_status, status)

    def handle_incoming_call_response(self, accepted, dialog):
        dialog.destroy()
        if accepted:
            if self.chat_client.accept_call(self.peer_udp_port):
                self.show_call_window(is_caller=False)
        else:
            self.chat_client.reject_call()

    def show_incoming_call_dialog(self, payload):
        self.peer_udp_port = payload['udp_port']
        dialog = ctk.CTkToplevel(self)
        dialog.title("Incoming Call")
        dialog.geometry("300x150")
        dialog.transient(self)
        dialog.grab_set()
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.handle_incoming_call_response(False, dialog))

        dialog.columnconfigure(0, weight=1)
        dialog.rowconfigure(0, weight=1)

        main_frame = ctk.CTkFrame(dialog)
        main_frame.grid(row=0, column=0, sticky="nsew", padx=10, pady=10)
        main_frame.columnconfigure((0, 1), weight=1)

        label = ctk.CTkLabel(main_frame, text=f"Incoming call from peer.\nAccept?")
        label.grid(row=0, column=0, columnspan=2, pady=10)

        accept_btn = ctk.CTkButton(main_frame, text="Accept", command=lambda: self.handle_incoming_call_response(True, dialog))
        accept_btn.grid(row=1, column=0, padx=10, pady=10)
        reject_btn = ctk.CTkButton(main_frame, text="Reject", command=lambda: self.handle_incoming_call_response(False, dialog), fg_color="#D32F2F")
        reject_btn.grid(row=1, column=1, padx=10, pady=10)

    def show_call_window(self, is_caller):
        if hasattr(self, 'call_window') and self.call_window.winfo_exists():
            self.call_window.focus()
            return
        
        self.call_window = CallWindow(self, self.chat_client)
        if is_caller:
            self.call_window.update_status("Ringing...")

class CallWindow(ctk.CTkToplevel):
    def __init__(self, master, chat_client):
        super().__init__(master)
        self.chat_client = chat_client
        self.title("Voice Call")
        self.geometry("300x150")
        self.protocol("WM_DELETE_WINDOW", self.hang_up)
        self.grab_set()

        self.status_label = ctk.CTkLabel(self, text="Connecting...", font=("Arial", 16))
        self.status_label.pack(pady=20, padx=20)

        hang_up_button = ctk.CTkButton(self, text="Hang Up", command=self.hang_up, fg_color="#D32F2F", hover_color="#B71C1C")
        hang_up_button.pack(pady=10)

    def hang_up(self):
        self.chat_client.end_call()
        self.destroy()

    def update_status(self, status):
        if self.winfo_exists():
            self.status_label.configure(text=status)
            if "ended" in status.lower() or "rejected" in status.lower() or "failed" in status.lower():
                self.after(2000, self.destroy) # Close window after 2 seconds


if __name__ == "__main__":
    ctk.set_appearance_mode("dark")
    app = ChatApp()
    app.mainloop() 