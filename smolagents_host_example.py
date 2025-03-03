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
import logging
import signal
import time
from typing import Optional

# smolagents / agent_link imports
from smolagents.agents import CodeAgent
from smolagents import DuckDuckGoSearchTool, HfApiModel
from agent_link import ConnectionConfig, AgentNode, Audience
from agent_link.config import AuthMethod

# Our separately defined decorator
from agent_link.decorators import smolagent_message_handler

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

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
# 2) Create and connect an AgentNode
# -------------------------------------------------------------------
room_id = os.getenv("ROOM_ID", "my_chat_room")
agent_id = os.getenv("HOST_ID")  # Optional, will be random UUID if not provided
node = AgentNode(config=config, room_id=room_id, agent_id=agent_id)

# We can query our randomly (or manually) assigned agent_id:
logger.info(f"My agent_id is {node.agent_id}")

# -------------------------------------------------------------------
# 3) Create a smolagent
# -------------------------------------------------------------------
model = HfApiModel()
my_agent = CodeAgent(tools=[DuckDuckGoSearchTool()], model=model)

# -------------------------------------------------------------------
# 4) Define a user handler and apply the decorator
# -------------------------------------------------------------------
@smolagent_message_handler(my_agent, node)
def handle_incoming(message, agent_response):
    """
    Optionally modify or log the agent's response.
    Return None to keep the smolagent's response as-is.
    """
    logger.info(f"Received message from {message.sender_id}: {str(message.content)[:50]}...")
    
    if "urgent" in str(message.content).lower():
        return f"(URGENT) {agent_response}"
    return None

# -------------------------------------------------------------------
# 5) Join the MQTT room and register the handler
# -------------------------------------------------------------------
def main():
    # Set up signal handlers for graceful shutdown
    def signal_handler(sig, frame):
        logger.info("Received shutdown signal, exiting...")
        node.leave()
        exit(0)
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Connect to MQTT and register our handler
        node.join()
        node.add_message_handler(handle_incoming)
        
        # Send an initial message to let everyone know we're here
        node.send_message(f"Hello! I'm a CodeAgent ({node.agent_id}) and I've joined the room. " 
                         "Ask me coding questions or mention 'urgent' for priority responses.")
        
        logger.info(f"Agent started successfully in room {room_id}")
        
        # Keep the main thread alive
        while True:
            # The MQTT client runs in its own thread, so we just need to keep this one alive
            time.sleep(1)
    
    except Exception as e:
        logger.error(f"Error in main loop: {e}")
    finally:
        node.leave()
        logger.info("Agent has left the room")

if __name__ == "__main__":
    main()