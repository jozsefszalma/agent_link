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


import pytest
import json
import time
from unittest.mock import patch, MagicMock, call

from agent_link import AgentNode, Audience, Message, ConnectionConfig
from agent_link.config import QoSLevel
from agent_link.a2a import (
    A2AEnvelope,
    create_send_message_request,
    create_text_message,
)

class TestAgentNode:
    def test_init(self, test_config):
        """Test initializing AgentNode"""
        with patch('agent_link.node.AgentLink') as mock_agent_link:
            room_id = "test-room"
            agent_id = "test-agent"
            
            node = AgentNode(
                config=test_config,
                room_id=room_id,
                agent_id=agent_id
            )
            
            # Check client creation
            mock_agent_link.assert_called_once_with(test_config)
            
            # Check instance variables
            assert node.room_id == room_id
            assert node.agent_id == agent_id
            assert node._group_topic == f"rooms/{room_id}/group"
            assert node._direct_topic == f"rooms/{room_id}/direct/{agent_id}"
            assert node._joined is False
            assert node._message_handlers == []

    def test_init_with_generated_ids(self, test_config):
        """Test initializing AgentNode with auto-generated IDs"""
        with patch('agent_link.node.AgentLink'):
            # No room_id or agent_id provided, should generate UUIDs
            node = AgentNode(config=test_config)
            
            assert node.room_id is not None
            assert node.agent_id is not None
            assert "rooms/" in node._group_topic
            assert "direct/" in node._direct_topic

    def test_add_message_handler(self, test_config):
        """Test adding message handlers"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(config=test_config)
            
            # Add handlers
            handler1 = lambda msg: None
            handler2 = lambda msg: "response"
            
            node.add_message_handler(handler1)
            node.add_message_handler(handler2)
            
            assert len(node._message_handlers) == 2
            assert node._message_handlers[0] is handler1
            assert node._message_handlers[1] is handler2

    def test_join(self, test_config, mock_agent_link):
        """Test joining a room"""
        node = AgentNode(config=test_config)
        
        result = node.join()
        
        # Check result
        assert result is True
        assert node._joined is True
        
        # Verify calls
        mock_agent_link.connect.assert_called_once()
        
        # Should subscribe to group and direct topics
        assert mock_agent_link.subscribe.call_count == 2
        
        # Check group subscription
        group_call = mock_agent_link.subscribe.call_args_list[0]
        assert group_call[1]["topic"] == node._group_topic
        assert group_call[1]["qos"] == node.qos
        
        # Check direct subscription
        direct_call = mock_agent_link.subscribe.call_args_list[1]  
        assert direct_call[1]["topic"] == node._direct_topic
        assert direct_call[1]["qos"] == node.qos

    def test_join_when_already_joined(self, test_config, mock_agent_link):
        """Test joining when already joined"""
        node = AgentNode(config=test_config)
        node._joined = True
        
        result = node.join()
        
        # Should return True but not do anything
        assert result is True
        mock_agent_link.connect.assert_not_called()
        mock_agent_link.subscribe.assert_not_called()

    def test_leave(self, test_config, mock_agent_link):
        """Test leaving a room"""
        node = AgentNode(config=test_config)
        node._joined = True
        
        result = node.leave()
        
        # Check result
        assert result is True
        assert node._joined is False
        
        # Verify calls
        assert mock_agent_link.unsubscribe.call_count == 2
        mock_agent_link.disconnect.assert_called_once()

    def test_leave_when_not_joined(self, test_config, mock_agent_link):
        """Test leaving when not joined"""
        node = AgentNode(config=test_config)
        node._joined = False
        
        result = node.leave()
        
        # Should return True but not do anything
        assert result is True
        mock_agent_link.unsubscribe.assert_not_called()
        mock_agent_link.disconnect.assert_not_called()

    def test_send_message_group(self, test_config, mock_agent_link):
        """Test sending a group message"""
        node = AgentNode(
            config=test_config,
            room_id="test-room",
            agent_id="test-agent"
        )
        node._joined = True
        
        content = "Hello, world!"
        
        result = node.send_message(content=content, audience=Audience.EVERYONE)
        
        # Just check we got a string ID back
        assert isinstance(result, str)
        
        # Verify publish was called
        mock_agent_link.publish.assert_called_once()
        call_args = mock_agent_link.publish.call_args[1]
        
        assert call_args["topic"] == node._group_topic
        
        # Verify message contents
        payload = call_args["payload"]
        assert payload["sender_id"] == node.agent_id
        assert payload["content"] == content
        assert payload["audience"] == Audience.EVERYONE.value
        assert "timestamp" in payload
        assert "message_id" in payload

    def test_send_message_direct(self, test_config, mock_agent_link):
        """Test sending a direct message"""
        node = AgentNode(
            config=test_config,
            room_id="test-room",
            agent_id="test-agent"
        )
        node._joined = True
        
        content = "Hello, recipient!"
        recipient_id = "recipient-agent"
        
        result = node.send_message(
            content=content,
            audience=Audience.DIRECT,
            recipient_id=recipient_id
        )
        
        # Just check we got a string ID back
        assert isinstance(result, str)
        
        # Verify publish was called with the right arguments
        mock_agent_link.publish.assert_called_once()
        call_args = mock_agent_link.publish.call_args[1]
        
        # Check it's sending to the right direct topic
        expected_topic = f"rooms/test-room/direct/{recipient_id}"
        assert call_args["topic"] == expected_topic
        
        # Verify message contents
        payload = call_args["payload"]
        assert payload["sender_id"] == node.agent_id
        assert payload["content"] == content
        assert payload["audience"] == Audience.DIRECT.value
        assert payload["recipient_id"] == recipient_id

    def test_send_message_with_reply(self, test_config, mock_agent_link):
        """Test sending a message as a reply"""
        node = AgentNode(config=test_config)
        node._joined = True
        
        content = "This is a reply"
        in_reply_to = "original-message-id"
        
        result = node.send_message(
            content=content,
            in_reply_to=in_reply_to
        )
        
        # Verify message contents includes reply reference
        payload = mock_agent_link.publish.call_args[1]["payload"]
        assert payload["in_reply_to"] == in_reply_to

    def test_send_message_not_joined(self, test_config):
        """Test sending a message when not joined"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(config=test_config)
            node._joined = False
            
            with pytest.raises(ConnectionError):
                node.send_message("Test message")

    def test_send_direct_message_without_recipient(self, test_config):
        """Test sending a direct message without recipient ID"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(config=test_config)
            node._joined = True
            
            with pytest.raises(ValueError):
                node.send_message(
                    content="Test message",
                    audience=Audience.DIRECT,
                    recipient_id=None
                )

    def test_handle_message(self, test_config):
        """Test handling incoming messages"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(
                config=test_config,
                agent_id="test-agent"
            )
            
            # Create handlers
            handler1 = MagicMock(return_value=None)
            handler2 = MagicMock(return_value="Response")
            
            # Register handlers
            node.add_message_handler(handler1)
            node.add_message_handler(handler2)
            
            # Create message payload
            topic = f"rooms/{node.room_id}/group"
            payload = {
                "sender_id": "other-agent",
                "content": "Hello!",
                "timestamp": time.time(),
                "message_id": "msg-123",
                "audience": Audience.EVERYONE.value,
            }
            
            # Mock the send_message method
            node.send_message = MagicMock()
            
            # Call handler
            node._handle_message(topic, payload)
            
            # Check both handlers were called
            handler1.assert_called_once()
            handler2.assert_called_once()
            
            # Check message object passed to handlers
            message = handler1.call_args[0][0]
            assert isinstance(message, Message)
            assert message.sender_id == "other-agent"
            assert message.content == "Hello!"
            assert message.audience == Audience.EVERYONE
            
            # Check response was sent
            node.send_message.assert_called_once()
            call_args = node.send_message.call_args[1]
            assert call_args["content"] == "Response"
            assert call_args["audience"] == Audience.EVERYONE
            assert call_args["in_reply_to"] == "msg-123"

    def test_handle_direct_message(self, test_config):
        """Test handling direct messages"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(
                config=test_config,
                agent_id="test-agent"
            )
            
            # Create handler
            handler = MagicMock(return_value="Direct response")
            
            # Register handler
            node.add_message_handler(handler)
            
            # Create message payload
            topic = f"rooms/{node.room_id}/direct/{node.agent_id}"
            payload = {
                "sender_id": "other-agent",
                "content": "Direct message",
                "timestamp": time.time(),
                "message_id": "msg-456",
                "audience": Audience.DIRECT.value,
                "recipient_id": node.agent_id
            }
            
            # Mock the send_message method
            node.send_message = MagicMock()
            
            # Call handler
            node._handle_message(topic, payload)
            
            # Check handler was called
            handler.assert_called_once()
            
            # Check direct response was sent
            node.send_message.assert_called_once()
            call_args = node.send_message.call_args[1]
            assert call_args["content"] == "Direct response"
            assert call_args["audience"] == Audience.DIRECT
            assert call_args["recipient_id"] == "other-agent"
            assert call_args["in_reply_to"] == "msg-456"

    def test_ignore_own_messages(self, test_config):
        """Test that own messages are ignored"""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(
                config=test_config,
                agent_id="test-agent"
            )
            
            handler = MagicMock()
            node.add_message_handler(handler)
            
            # Create message from self
            payload = {
                "sender_id": node.agent_id,  # Same as node's agent_id
                "content": "My message",
                "timestamp": time.time(),
                "message_id": "msg-123",
                "audience": Audience.EVERYONE.value,
            }
            
            # Call handler
            node._handle_message(f"rooms/{node.room_id}/group", payload)
            
            # Handler should not be called for own messages
            handler.assert_not_called()

    def test_send_a2a_request(self, test_config, mock_agent_link):
        """Test sending an A2A request"""
        node = AgentNode(
            config=test_config,
            room_id="a2a-room",
            agent_id="agent-sender",
        )
        node._joined = True

        request_id = node.send_a2a_request(
            text="Hello via A2A",
            audience=Audience.DIRECT,
            recipient_id="agent-recipient",
            message_metadata={"sender_id": "agent-sender"},
        )

        assert isinstance(request_id, (str, int))

        mock_agent_link.publish.assert_called_once()
        call_args = mock_agent_link.publish.call_args[1]
        assert call_args["topic"] == "rooms/a2a-room/direct/agent-recipient"
        payload = call_args["payload"]
        assert payload["jsonrpc"] == "2.0"
        assert payload["method"] == "message/send"
        assert payload["params"]["message"]["metadata"]["sender_id"] == "agent-sender"
        assert payload["params"]["message"]["parts"][0]["text"] == "Hello via A2A"

    def test_send_a2a_request_adds_sender_metadata_by_default(self, test_config, mock_agent_link):
        """A2A requests include sender metadata when none is provided."""
        node = AgentNode(
            config=test_config,
            room_id="a2a-room",
            agent_id="agent-sender",
        )
        node._joined = True

        node.send_a2a_request(
            text="Hello via A2A",
            audience=Audience.DIRECT,
            recipient_id="agent-recipient",
        )

        payload = mock_agent_link.publish.call_args[1]["payload"]
        metadata = payload["params"]["message"]["metadata"]
        assert metadata["senderId"] == "agent-sender"

    def test_handle_a2a_message(self, test_config):
        """Ensure incoming A2A payloads are parsed and passed to handlers."""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(config=test_config, agent_id="agent")
            handler = MagicMock(return_value=None)
            node.add_message_handler(handler)

            incoming = create_text_message("Ping", role="user", metadata={"sender_id": "peer"})
            envelope = create_send_message_request(message=incoming, request_id="req-123")

            topic = f"rooms/{node.room_id}/direct/{node.agent_id}"
            node._handle_message(topic, envelope.to_dict())

            handler.assert_called_once()
            message = handler.call_args[0][0]
            assert isinstance(message.a2a_envelope, A2AEnvelope)
            assert message.content == "Ping"
            assert message.sender_id == "peer"
            assert message.audience == Audience.DIRECT

    def test_handler_returning_a2a_message(self, test_config):
        """If a handler returns an A2A message, respond with a JSON-RPC result."""
        with patch('agent_link.node.AgentLink'):
            node = AgentNode(config=test_config, agent_id="agent")
            outgoing = create_text_message("Pong", role="agent")

            handler = MagicMock(return_value=outgoing)
            node.add_message_handler(handler)

            incoming = create_text_message("Ping", role="user", metadata={"sender_id": "peer"})
            envelope = create_send_message_request(message=incoming, request_id="req-234")

            topic = f"rooms/{node.room_id}/direct/{node.agent_id}"
            node._handle_message(topic, envelope.to_dict())

            node.client.publish.assert_called_once()
            publish_kwargs = node.client.publish.call_args.kwargs
            assert publish_kwargs["topic"] == f"rooms/{node.room_id}/direct/peer"
            payload = publish_kwargs["payload"]
            assert payload["jsonrpc"] == "2.0"
            assert payload["id"] == "req-234"
            assert payload["result"]["parts"][0]["text"] == "Pong"
            assert payload["result"]["metadata"]["senderId"] == "agent"
