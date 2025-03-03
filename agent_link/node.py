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

# Standard imports
import uuid
import time
import json
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Union, Set
from dataclasses import dataclass, field

# Package imports
from .client import AgentLink
from .config import ConnectionConfig, QoSLevel

logger = logging.getLogger(__name__)

class Audience(Enum):
    """Audience types for chat messages."""
    EVERYONE = "everyone"  # Message to everyone in the room
    DIRECT = "direct"      # Direct message to a specific agent


@dataclass
class Message:
    """Represents a chat message."""
    sender_id: str
    content: Any
    timestamp: float = field(default_factory=time.time)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    in_reply_to: Optional[str] = None  # Message ID this is replying to
    audience: Audience = Audience.EVERYONE
    recipient_id: Optional[str] = None  # For direct messages


class AgentNode:
    def __init__(
        self, 
        config: ConnectionConfig,
        room_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        #mode: AgentMode = AgentMode.HYBRID,
        #function: Optional[Callable] = None,
        respond_to_group: bool = True,
        respond_to_direct: bool = True,
        max_conversation_length: int = 50,
        qos: QoSLevel = QoSLevel.AT_LEAST_ONCE,
        #include_metadata: bool = True
    ):
        self.client = AgentLink(config)
        self.room_id = room_id or str(uuid.uuid4())
        self.agent_id = agent_id or str(uuid.uuid4())
        #self.mode = mode
        #self.function = function
        self.respond_to_group = respond_to_group
        self.respond_to_direct = respond_to_direct
        self.max_conversation_length = max_conversation_length
        self.qos = qos
        #self.include_metadata = include_metadata        

        # Construct topic patterns
        self._group_topic = f"rooms/{self.room_id}/group"
        self._direct_topic = f"rooms/{self.room_id}/direct/{self.agent_id}"

        # Track connections and conversations
        self._joined = False
        #self._conversations: Dict[str, List[Message]] = {}
        self._message_handlers: List[Callable[[Message], Optional[Any]]] = []

    def add_message_handler(self, handler: Callable[[Message], Optional[Any]]) -> None:
        """
        Add a message handler function.
        
        Args:
            handler: Function that processes messages and optionally returns a response
        """
        self._message_handlers.append(handler)

    def join(self) -> bool:
        """
        Join the room
        
        Returns:
            bool: True if successfully joined
        
        Raises:
            ConnectionError: If failed to connect to the broker
        """
        if self._joined:
            logger.info("Already joined the room")
            return True
        
        # Connect to broker
        self.client.connect()
        
        # Subscribe based on settings

        if self.respond_to_group:
            logger.info(f"Subscribing to group messages: {self._group_topic}")
            self.client.subscribe(
                topic=self._group_topic,
                callback=self._handle_message,
                qos=self.qos
            )
        
        if self.respond_to_direct:
            logger.info(f"Subscribing to direct messages: {self._direct_topic}")
            self.client.subscribe(
                topic=self._direct_topic,
                callback=self._handle_message,
                qos=self.qos
            )
        
        
        self._joined = True
        
        
        return True
    
    def leave(self) -> bool:
        """
        Leave the room.
        
        Returns:
            bool: True if successfully left
        """
        if not self._joined:
            logger.info("Not in a room")
            return True
        
        try:
            # Unsubscribe from all topics
            if self.respond_to_group:
                self.client.unsubscribe(self._group_topic)
            
            if self.respond_to_direct:
                self.client.unsubscribe(self._direct_topic)
            
            
            self.client.disconnect()
            self._joined = False
            return True
            
        except Exception as e:
            logger.error(f"Error leaving room: {e}")
            return False
        
    def send_message(
        self, 
        content: Any, 
        audience: Audience = Audience.EVERYONE,
        recipient_id: Optional[str] = None,
        in_reply_to: Optional[str] = None
        ) -> Optional[str]:
        """
        Send a message to the room or directly to an agent.
        
        Args:
            content: Message content (can be string, dict, or other serializable type)
            audience: Whether to send to everyone or directly to an agent
            recipient_id: ID of recipient agent for direct messages
            in_reply_to: ID of the message this is replying to
            
        Returns:
            Optional[str]: Message ID if successful, None if failed
            
        Raises:
            ValueError: If sending a direct message without a recipient
            ConnectionError: If not connected to the broker
        """
        if not self._joined:
            raise ConnectionError("Not joined to a room")
        
        if audience == Audience.DIRECT and not recipient_id:
            raise ValueError("Recipient ID required for direct messages")
        
        # Create message
        message = Message(
            sender_id=self.agent_id,
            content=content,
            audience=audience,
            recipient_id=recipient_id,
            in_reply_to=in_reply_to,
        )
        
        try:
            # Determine target topic
            if audience == Audience.EVERYONE:
                topic = self._group_topic
            else:
                topic = f"rooms/{self.room_id}/direct/{recipient_id}"
            
            
            # Use standard chat format 
            message_dict = {
                "sender_id": message.sender_id,
                "content": message.content,
                "timestamp": message.timestamp,
                "message_id": message.message_id,
                "in_reply_to": message.in_reply_to,
                "audience": message.audience.value,
                "recipient_id": message.recipient_id,
            }
           
            # Publish message
            self.client.publish(
                topic=topic,
                payload=message_dict,
                qos=self.qos
            )
            
            logger.debug(f"Sent message {message.message_id} to {topic}")
            return message.message_id
            
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None        

    def _handle_message(self, topic: str, payload: Dict[str, Any]) -> None:
        """Handle incoming direct messages in chat mode."""
        try:
            sender_id = payload["sender_id"]
            # Skip our own messages
            if sender_id == self.agent_id:
                return
               
            message = Message(
                sender_id=sender_id,
                content=payload["content"],
                timestamp=payload["timestamp"],
                message_id=payload["message_id"],
                in_reply_to=payload.get("in_reply_to"),
                audience = Audience(payload.get("audience", "direct")),
                recipient_id=self.agent_id,
            )
            
            logger.info(f"Received message from {message.sender_id}: {str(message.content)[:50]}...")
            

            # Process through all handlers
            for handler in self._message_handlers:
                try:
                    response = handler(message)
                    if response is not None:
                        # Send response
                        self.send_message(
                            content=response,
                            audience=message.audience,
                            recipient_id=message.sender_id if message.audience == Audience.DIRECT else None,
                            in_reply_to=message.message_id
                        )
                except Exception as e:
                    logger.error(f"Error in message handler: {e}")
            
        except KeyError as e:
            logger.warning(f"Malformed message received: {e}")        