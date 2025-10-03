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
import logging
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Sequence, Union
from dataclasses import dataclass, field

# Package imports
from .client import AgentLink
from .config import ConnectionConfig, QoSLevel
from .a2a import (
    A2AEnvelope,
    A2AMessage,
    A2APart,
    A2ARole,
    MessageSendConfiguration,
    SendMessageRequest,
    create_send_message_request,
    create_text_part,
    derive_sender_id_from_message,
    is_a2a_envelope,
    parse_a2a_envelope,
)

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
    raw_payload: Optional[Any] = None
    a2a_envelope: Optional[A2AEnvelope] = None


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

    def send_a2a_request(
        self,
        *,
        text: Optional[str] = None,
        message: Optional[A2AMessage] = None,
        parts: Optional[Sequence[A2APart]] = None,
        role: A2ARole = "user",
        audience: Audience = Audience.DIRECT,
        recipient_id: Optional[str] = None,
        configuration: Optional[MessageSendConfiguration] = None,
        message_metadata: Optional[Dict[str, Any]] = None,
        request_metadata: Optional[Dict[str, Any]] = None,
        extensions: Optional[Sequence[str]] = None,
        reference_task_ids: Optional[Sequence[str]] = None,
        task_id: Optional[str] = None,
        context_id: Optional[str] = None,
        request_id: Optional[Union[str, int]] = None,
        message_id: Optional[str] = None,
    ) -> Union[str, int]:
        """Send an A2A ``message/send`` JSON-RPC request."""

        if not self._joined:
            raise ConnectionError("Not joined to a room")

        if audience == Audience.DIRECT and not recipient_id:
            raise ValueError("Recipient ID required for direct A2A messages")

        if message_metadata is not None and not isinstance(message_metadata, dict):
            raise ValueError("message_metadata must be a dictionary if provided")

        if request_metadata is not None and not isinstance(request_metadata, dict):
            raise ValueError("request_metadata must be a dictionary if provided")

        if role not in ("user", "agent"):
            raise ValueError("role must be either 'user' or 'agent'")

        normalized_extensions = None
        if extensions is not None:
            normalized_extensions = list(extensions)
            if not all(isinstance(item, str) for item in normalized_extensions):
                raise ValueError("All extension identifiers must be strings")

        normalized_reference_ids = None
        if reference_task_ids is not None:
            normalized_reference_ids = list(reference_task_ids)
            if not all(isinstance(item, str) for item in normalized_reference_ids):
                raise ValueError("All reference task identifiers must be strings")

        part_list: List[A2APart] = []
        if parts is not None:
            part_list = list(parts)
            if not all(isinstance(part, A2APart) for part in part_list):
                raise ValueError("All parts must be instances of A2APart")

        if text is not None:
            part_list.append(create_text_part(text))

        if message is None:
            if not part_list:
                raise ValueError("Either 'message', 'parts', or 'text' must be provided")
            constructed_message = A2AMessage(
                role=role,
                parts=part_list,
                message_id=message_id or str(uuid.uuid4()),
                metadata=message_metadata,
                extensions=normalized_extensions,
                reference_task_ids=normalized_reference_ids,
                task_id=task_id,
                context_id=context_id,
            )
        else:
            constructed_message = message
            if message_metadata:
                merged_metadata = {**(constructed_message.metadata or {}), **message_metadata}
                constructed_message = constructed_message.with_updates(metadata=merged_metadata)
            if normalized_extensions is not None:
                constructed_message = constructed_message.with_updates(extensions=normalized_extensions)
            if normalized_reference_ids is not None:
                constructed_message = constructed_message.with_updates(reference_task_ids=normalized_reference_ids)
            if task_id is not None:
                constructed_message = constructed_message.with_updates(task_id=task_id)
            if context_id is not None:
                constructed_message = constructed_message.with_updates(context_id=context_id)
            if message_id is not None and message_id != constructed_message.message_id:
                constructed_message = constructed_message.with_updates(message_id=message_id)

        request = create_send_message_request(
            constructed_message,
            request_id=request_id,
            configuration=configuration,
            metadata=request_metadata,
        )

        if audience == Audience.EVERYONE:
            topic = self._group_topic
        else:
            topic = f"rooms/{self.room_id}/direct/{recipient_id}"

        self.client.publish(
            topic=topic,
            payload=request.to_dict(),
            qos=self.qos,
        )
        logger.debug(f"Sent A2A request {request.id} to {topic}")
        return request.id

    def _handle_message(self, topic: str, payload: Dict[str, Any]) -> None:
        """Handle incoming messages in chat or A2A format."""

        if not isinstance(payload, dict):
            logger.warning(f"Ignoring non-dict payload on {topic}")
            return

        is_direct_topic = topic.startswith(f"rooms/{self.room_id}/direct/")
        audience_value = payload.get("audience")
        if isinstance(audience_value, str):
            try:
                audience = Audience(audience_value)
            except ValueError:
                audience = Audience.DIRECT if is_direct_topic else Audience.EVERYONE
        else:
            audience = Audience.DIRECT if is_direct_topic else Audience.EVERYONE

        recipient_id = payload.get("recipient_id") if audience == Audience.DIRECT else None
        if audience == Audience.DIRECT and recipient_id is None:
            recipient_id = self.agent_id

        timestamp = payload.get("timestamp", time.time())
        a2a_envelope = parse_a2a_envelope(payload)
        message: Optional[Message] = None

        if a2a_envelope and a2a_envelope.message:
            message_obj = a2a_envelope.message
            sender_id = derive_sender_id_from_message(message_obj)
            if sender_id == self.agent_id:
                return

            content = message_obj.primary_text or message_obj.to_dict()
            in_reply_to = None
            metadata = message_obj.metadata or {}
            for key in ("in_reply_to", "inReplyTo", "reply_to", "replyTo"):
                value = metadata.get(key)
                if isinstance(value, str):
                    in_reply_to = value
                    break

            message = Message(
                sender_id=sender_id,
                content=content,
                timestamp=timestamp,
                message_id=message_obj.message_id,
                in_reply_to=in_reply_to,
                audience=audience,
                recipient_id=recipient_id,
                raw_payload=payload,
                a2a_envelope=a2a_envelope,
            )
        else:
            try:
                sender_id = payload["sender_id"]
                if sender_id == self.agent_id:
                    return

                message_id = (
                    payload.get("message_id")
                    or payload.get("messageId")
                    or str(uuid.uuid4())
                )
                content = payload["content"]
            except KeyError as exc:
                logger.warning(f"Malformed message received: {exc}")
                return

            message = Message(
                sender_id=sender_id,
                content=content,
                timestamp=timestamp,
                message_id=message_id,
                in_reply_to=payload.get("in_reply_to") or payload.get("inReplyTo"),
                audience=audience,
                recipient_id=recipient_id,
                raw_payload=payload,
            )

        logger.info(
            "Received message from %s: %s...",
            message.sender_id,
            str(message.content)[:50],
        )

        for handler in self._message_handlers:
            try:
                response = handler(message)
                if response is None:
                    continue

                if isinstance(response, SendMessageRequest):
                    response_payload = response.to_dict()
                    target_topic = (
                        self._group_topic
                        if message.audience == Audience.EVERYONE
                        else f"rooms/{self.room_id}/direct/{message.sender_id}"
                    )
                    self.client.publish(
                        topic=target_topic,
                        payload=response_payload,
                        qos=self.qos,
                    )
                    continue

                if isinstance(response, A2AMessage):
                    self.send_a2a_request(
                        message=response,
                        audience=message.audience,
                        recipient_id=(
                            message.sender_id if message.audience == Audience.DIRECT else None
                        ),
                    )
                    continue

                if isinstance(response, dict) and is_a2a_envelope(response):
                    target_topic = (
                        self._group_topic
                        if message.audience == Audience.EVERYONE
                        else f"rooms/{self.room_id}/direct/{message.sender_id}"
                    )
                    self.client.publish(
                        topic=target_topic,
                        payload=response,
                        qos=self.qos,
                    )
                    continue

                self.send_message(
                    content=response,
                    audience=message.audience,
                    recipient_id=(
                        message.sender_id if message.audience == Audience.DIRECT else None
                    ),
                    in_reply_to=message.message_id,
                )
            except Exception as exc:  # pragma: no cover - handler safety net
                logger.error(f"Error in message handler: {exc}")