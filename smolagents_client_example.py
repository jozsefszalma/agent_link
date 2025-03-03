# Copyright 2025 Jozsef Szalma

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import sys
import signal
import time
import logging
from threading import Event

from agent_link import ConnectionConfig, AgentNode, Audience, Message
from agent_link.config import AuthMethod

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Exit flag for clean shutdown
exit_flag = Event()

def main():
    # -------------------------------------------------------------------
    # 1) Connection setup using environment variables
    # -------------------------------------------------------------------
    config = ConnectionConfig(
        broker=os.getenv("MQTT_BROKER"),
        port=int(os.getenv("MQTT_PORT", "1883")),
        username=os.getenv("MQTT_USER"),
        password=os.getenv("MQTT_PASS"),
        use_tls=os.getenv("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes"),
        auth_method=AuthMethod.USERPASS,
    )

    # -------------------------------------------------------------------
    # 2) Create and connect an AgentNode for the client
    # -------------------------------------------------------------------
    room_id = os.getenv("ROOM_ID")
    client_id = f"human_client_{int(time.time())}"  # Generate a unique ID
    host_id = os.getenv("HOST_ID")  # The ID of the agent we want to talk to
    
    client_node = AgentNode(config=config, room_id=room_id, agent_id=client_id)
    logger.info(f"Client ID: {client_id}")
    logger.info(f"Room ID: {room_id}")
    
    if host_id:
        logger.info(f"Will send direct messages to host ID: {host_id}")
    else:
        logger.info("No HOST_ID specified, will send messages to everyone in the room")

    # -------------------------------------------------------------------
    # 3) Handle incoming messages
    # -------------------------------------------------------------------
    def handle_message(message: Message) -> None:
        """Print incoming messages"""
        # Don't respond to our own messages
        if message.sender_id == client_id:
            return
        
        # Print the message
        print(f"\n[{message.sender_id}]: {message.content}")
        print("\nYou: ", end="", flush=True)  # Reset prompt
        
        return None  # No response needed

    # -------------------------------------------------------------------
    # 4) Set up exit handler
    # -------------------------------------------------------------------
    def signal_handler(sig, frame):
        logger.info("Shutting down client...")
        exit_flag.set()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        # Join the room and register our message handler
        client_node.join()
        client_node.add_message_handler(handle_message)
        
        print("\n=== MQTT Chat Client ===")
        print(f"Connected to room: {room_id}")
        if host_id:
            print(f"Sending direct messages to: {host_id}")
        else:
            print("Sending messages to everyone in the room")
        print("Type your messages and press Enter to send")
        print("Press Ctrl+C to exit")
        print("======================\n")
        
        # Send an initial notification
        #client_node.send_message(f"Human client {client_id} has joined the chat")
        
        # Main loop: Read user input and send messages
        while not exit_flag.is_set():
            try:
                print("You: ", end="", flush=True)
                user_input = input()
                
                if not user_input.strip():
                    continue
                    
                if user_input.lower() in ('exit', 'quit'):
                    break
                
                # Determine if this is a direct message or group message
                if host_id:
                    # Send direct message to the specific agent
                    client_node.send_message(
                        content=user_input,
                        audience=Audience.DIRECT,
                        recipient_id=host_id
                    )
                else:
                    # Send to everyone in the room
                    client_node.send_message(content=user_input)
                    
            except EOFError:
                break  # Handle Ctrl+D
                
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        # Send a goodbye message and leave the room
        #client_node.send_message("Human client has left the chat")
        client_node.leave()
        logger.info("Client disconnected")

if __name__ == "__main__":
    main()