# agent_link
a Python Library for Distributed AI Agent Communications   

![Talk to my Agent meme](https://github.com/jozsefszalma/agent_link/blob/main/images/arnold.jpg?raw=true)


## Origin Story
The inspiration for this project came from the extremely cool [gibberlink](https://github.com/PennyroyalTea/gibberlink) demo and originally started as a joke:
![Skypenet joke on Linkedin](https://github.com/jozsefszalma/agent_link/blob/main/images/skypenet.png?raw=true)

Since I don't want to anger the nice folks in Redmond, I decided NOT to call it Skypenet in the end...

## Purpose
The purpose of this library is to enable AI agents to talk to each other over the internet via the MQTT protocol. This allows for:

- **Distributed Agent Systems**: Connect AI agents running on different machines anywhere in the world
- **Multi-Agent Conversations**: Enable groups of specialized agents to collaborate on complex tasks
- **Human-Agent Interaction**: Provide interfaces for humans to communicate with agent networks
- **Persistent Communication Channels**: Create long-lived communication streams between agents  

The agents need to do a side-channel handshake (e.g. over the phone or via email etc) to exchange the ROOM_ID and the HOST_ID for this work.

## How It Works
### MQTT Protocol
MQTT (Message Queuing Telemetry Transport) is a lightweight, publish-subscribe network protocol designed for resource-constrained devices and low-bandwidth, high-latency networks - making it ideal for agent communications. Key benefits include:

- **Low Overhead**: Minimal packet size for efficient transmission
- **Publish/Subscribe Model**: Agents can publish to topics and subscribe to receive relevant messages
- **Quality of Service**: Configurable message delivery guarantees
- **Security**: Support for TLS encryption and authentication

## Limitations and Future Considerations

### Current Limitations
The primary limitation of this technology is the requirement for a common broker service. For agent-to-agent communication to work, all participants must connect to the same MQTT broker, creating potential centralization issues.

Ideally, a large player in the AI space like [Hugging Face](https://huggingface.co/huggingface) could serve as a universal provider of MQTT broker services, establishing a common "meeting place" for AI agents across the internet. This would create a standardized communication layer for AI systems regardless of their underlying models or implementations.   

Alternatively, a peer-to-peer layer like the [Matrix protocol](https://matrix.org/) could provide this infrastructure, eliminating the centralized broker dependency but requiring a dedicated server, such as [Synapse](https://github.com/element-hq/synapse), to manage network federation.

Without such a common infrastructure, agent networks would remain siloed within organizational boundaries, limiting the potential for truly open agent ecosystems.


### Communication Architecture

1. Agents connect to a shared MQTT broker using credentials
2. Messages are published to topic channels corresponding to rooms or direct messages
3. The broker routes messages to all subscribed agents
4. Responses can be directed to everyone in a room or specific agents

## Installation & Setup
### 1.  Install the Package
```bash
pip install ai-agent-link
```
### 2. Set Up MQTT Broker Access
Register for an account at an MQTT broker service. [HiveMQ Cloud](https://hivemq.cloud) offers a free tier sufficient for testing.

#### Broker Selection Guide:

- HiveMQ Cloud: Easy setup, free tier available
- CloudMQTT: Scalable options for production
- Mosquitto: Self-hosted option for complete control
- AWS IoT Core: Enterprise-grade for production systems
### 3. Configure Environment
Create a .env file with your MQTT broker credentials:
```
MQTT_BROKER=your-broker-instance.hivemq.cloud  # Broker hostname
MQTT_PORT=8883                                 # Usually 8883 for TLS connections
MQTT_USER=your_username                        # Your broker username
MQTT_PASS=your_password                        # Your broker password
MQTT_USE_TLS="true"                            # Use TLS encryption (recommended)
ROOM_ID=unique-room-identifier                 # Can be anything, UUIDs recommended
HOST_ID=unique-host-identifier                 # Agent ID of host/server agent,
```

## Quick Start Example
### Basic Agent Communication
```python
from agent_link import ConnectionConfig, AgentNode, Audience, Message
from agent_link.config import AuthMethod
import os

# 1. Create connection configuration
config = ConnectionConfig(
    broker=os.getenv("MQTT_BROKER"),
    port=int(os.getenv("MQTT_PORT", "1883")),
    username=os.getenv("MQTT_USER"),
    password=os.getenv("MQTT_PASS"),
    use_tls=True,
    auth_method=AuthMethod.USERPASS,
)

# 2. Create and connect an agent node
room_id = "my_test_room"
agent_id = "agent_001"
node = AgentNode(config=config, room_id=room_id, agent_id=agent_id)

# 3. Define a message handler
def handle_message(message: Message) -> str:
    print(f"Received from {message.sender_id}: {message.content}")
    return f"I received your message: {message.content}"

# 4. Join the room and register handler
node.join()
node.add_message_handler(handle_message)

# 5. Send a message to everyone in the room
node.send_message("Hello everyone, I've joined the room!")

# Keep the agent running
try:
    while True:
        time.sleep(1)
        pass  # Your main loop logic here
except KeyboardInterrupt:
    # Clean exit when terminated
    node.leave()
```

## Detailed Examples
### Human-Agent Chat Example
The repository includes two example scripts showing human-agent interaction:
**On Machine 1 (Agent Host):**
```bash
# Start the AI agent
python smolagents_host_example.py
```
**On Machine 2 (Human Client):**
```bash
# Start the human chat client
python smolagents_client_example.py
```
Both machines need the same MQTT broker credentials and room/host IDs in their .env files.
To be able to run these scripts as-is **you need to log into your Hugging Face account** using huggingface-cli login on the machine running the host example script.   
This is because the host script is using a (free) Hugging Face agent for the purposes of this demo.

### Smolagents Integration Example
The agent_link library can easily integrate with Hugging Face's smolagents library using the provided decorator.

```python
from smolagents.agents import CodeAgent
from smolagents import DuckDuckGoSearchTool, HfApiModel
from agent_link import ConnectionConfig, AgentNode
from agent_link.decorators import smolagent_message_handler

# Set up the smolagent
model = HfApiModel()
my_agent = CodeAgent(tools=[DuckDuckGoSearchTool()], model=model)

# Set up the agent_link node
node = AgentNode(config=config, room_id=room_id, agent_id=agent_id)
node.join()

# Define handler with the decorator
@smolagent_message_handler(my_agent, node)
def handle_incoming(message, agent_response):
    """
    Process incoming messages and optionally modify responses.
    
    Args:
        message: The incoming message object
        agent_response: The response generated by the smolagent
    
    Returns:
        Modified response or None to keep the original response
    """
    print(f"Processing message from {message.sender_id}")
    
    # Example of modifying responses based on content
    if "urgent" in str(message.content).lower():
        return f"[URGENT] {agent_response}"
    
    # Return None to use the smolagent's response as-is
    return None
```

## Core API Reference

### Main Classes

#### `ConnectionConfig`
Configuration settings for connecting to an MQTT broker.

```python
config = ConnectionConfig(
    broker="broker.example.com",    # Hostname of MQTT broker
    port=8883,                      # Port number
    use_tls=True,                   # Whether to use TLS encryption
    auth_method=AuthMethod.USERPASS,# Authentication method; NONE, USERPASS, TOKEN, CERT, API_KEY
    username="user",                # Username for auth
    password="pass",                # Password for auth
    client_id="my_client"           # Optional client ID
)
```   

#### `AgentNode`
The main class for agent communication.

```python
node = AgentNode(
    config=config,                  # ConnectionConfig object
    room_id="room_id",              # Room identifier
    agent_id="agent_id",            # Unique agent identifier
    respond_to_group=True,          # Whether to process group messages
    respond_to_direct=True,         # Whether to process direct messages
    qos=QoSLevel.AT_LEAST_ONCE      # Quality of Service level; AT_MOST_ONCE, AT_LEAST_ONCE or EXACTLY_ONCE
)
```

Methods:
- `join()`: Connect to broker and join the room
- `leave()`: Leave the room and disconnect
- `add_message_handler(handler)`: Add a function to process incoming messages
- `send_message(content, audience, recipient_id, in_reply_to)`: Send a message

#### `Message`
Represents a chat message between agents.

```python
message = Message(
    sender_id="agent_001",          # ID of message sender
    content="Hello world",          # Message content (any serializable type)
    timestamp=1234567890,           # Optional timestamp
    message_id="msg_12345",         # Optional message ID
    in_reply_to="msg_12344",        # Optional reference to previous message
    audience=Audience.EVERYONE,     # EVERYONE or DIRECT
    recipient_id="agent_002"        # Required for DIRECT messages
)
```


### Security Considerations
When using agent_link in production:

- Always use TLS encryption (set `use_tls=True`)
- Generate unique, random room IDs for each conversation
- Implement appropriate authentication for your agents
- Be cautious about what information is shared in agent communications

## Troubleshooting

### Common Issues

**Connection Failures**
- Verify MQTT broker hostname and port are correct
- Check username and password credentials
- Ensure firewall allows outbound connections to MQTT port

**Message Not Received**
- Verify room_id matches on all agents
- Check that the recipient_id is correct for direct messages
- Ensure the agent has joined the room before sending messages

**Performance Issues**
- Adjust Quality of Service level (QoS) for your use case
- Reduce message size by minimizing payload content
- Consider upgrading to a paid MQTT broker for production use

## Future Development
The roadmap for `agent_link` includes:

- **Complete documentation**: Expanding API documentation and examples (e.g. different auth options)
- **Additional integrations**: Support for more agent frameworks
- **Enhanced security**: E2E message encryption


## License and Acknowledgment
   Copyright 2025 Jozsef Szalma

   Licensed under the Apache License, Version 2.0 (the "License");
   you may not use this file except in compliance with the License.
   You may obtain a copy of the License at

       http://www.apache.org/licenses/LICENSE-2.0

   Unless required by applicable law or agreed to in writing, software
   distributed under the License is distributed on an "AS IS" BASIS,
   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
   See the License for the specific language governing permissions and
   limitations under the License.


### Acknowledgment
Dependencies:
- [Eclipse Paho MQTT Python library](https://github.com/eclipse-paho/paho.mqtt.python) 
- [Hugging Face smolagents](https://github.com/huggingface/smolagents)

