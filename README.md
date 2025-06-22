# P2P Encrypted Messenger

A secure, peer-to-peer (P2P) messaging application built with Python. It provides end-to-end encryption for all communications, including text messages, file transfers, and live voice calls, ensuring that only the sender and receiver can access the content.

## Features

- **End-to-End Encryption:** Uses the `cryptography` library (Fernet) to secure all data transmitted between peers.
- **Live Voice Calls:** Engage in real-time, encrypted voice conversations.
- **Text & Emoji Messaging:** Send and receive text messages with full emoji support.
- **Secure File Transfer:** Share images, documents, and other files securely.
- **Voice Messages:** Record and send encrypted voice notes.
- **No Central Server:** True peer-to-peer architecture means your data is never stored on a third-party server, maximizing privacy.
- **Modern UI:** A clean and user-friendly interface built with `customtkinter`.
- **Connection Management:** Handles connection requests, disconnects, and reconnections gracefully.

## How to Run

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/Parsaa404/P2P-Messenger.git
    cd P2P-Messenger
    ```

2.  **Install dependencies:**
    Make sure you have Python 3 installed. Then, install the required packages using the `requirements.txt` file.
    ```bash
    pip install -r requirements.txt
    ```

3.  **Run the application:**
    ```bash
    python ui.py
    ```

## How to Connect with a Peer

The connection process depends on whether you and your peer are on the same local network or on different networks (over the internet).

### Scenario 1: Both Users on the Same Local Network (e.g., same WiFi)

This is the simplest scenario.

1.  **User A (The "Listener"):**
    *   Runs the application.
    *   Selects **"Listen"** mode.
    *   Enters a port number (e.g., `9999`) and a strong, shared password.
    *   The application will display their **Local IP Address** (e.g., `192.168.1.5`). User A must send this IP address to User B.

2.  **User B (The "Connector"):**
    *   Runs the application.
    *   Selects **"Connect"** mode.
    *   Enters User A's **Local IP Address** (e.g., `192.168.1.5`).
    *   Enters the **same port number** (e.g., `9999`) and the **same shared password** that User A used.
    *   Clicks "Connect".

User A will receive a connection request, and upon accepting it, the encrypted chat will begin.

### Scenario 2: Users on Different Networks (over the Internet)

To connect over the internet, the user acting as the "Listener" must configure **Port Forwarding** on their router. This allows external traffic from the internet to be directed to their computer.

1.  **User A (The "Listener" - Must Configure Port Forwarding):**
    *   **Step 1: Find your Local IP.** Open Command Prompt (on Windows) and type `ipconfig` or Terminal (on macOS/Linux) and type `ifconfig`. Find the "IPv4 Address" - it usually looks like `192.168.x.x`.
    *   **Step 2: Access your router's admin page.** This is usually `192.168.1.1` or `192.168.0.1`. You can find the correct address (often called "Default Gateway") in the `ipconfig`/`ifconfig` output.
    *   **Step 3: Log in to your router.** The username/password are often on a sticker on the router itself (e.g., admin/admin, admin/password).
    *   **Step 4: Find the "Port Forwarding" settings.** This might be under "Advanced," "NAT," "Firewall," or "Virtual Server."
    *   **Step 5: Create a new port forwarding rule:**
        *   **Application/Service Name:** `P2P-Messenger` (or anything you like)
        *   **External Port / Start Port:** `9999` (the port you will use in the app)
        *   **Internal Port / End Port:** `9999` (the same port)
        *   **Protocol:** `TCP`
        *   **Device IP / Internal IP Address:** Your computer's **Local IP** from Step 1.
    *   **Step 6: Find your Public IP.** Go to a website like [whatismyip.com](https://www.whatismyip.com/). This is the address User B will use.
    *   **Step 7: Run the application.** Choose "Listen" mode and enter the port (`9999`) and a shared password.

2.  **User B (The "Connector"):**
    *   Runs the application.
    *   Selects **"Connect"** mode.
    *   Enters User A's **Public IP Address** (from Step 6).
    *   Enters the **same port number** (`9999`) and the **same shared password**.
    *   Clicks "Connect".

The connection will now be established across the internet.

## Technology Stack

- **Python:** Core programming language.
- **Sockets:** For low-level network communication (TCP/UDP).
- **CustomTkinter:** For the modern graphical user interface.
- **PyAudio:** For capturing and playing live audio and voice messages.
- **Cryptography (Fernet):** For symmetric end-to-end encryption.
- **Threading:** To handle network operations and the UI without blocking. 