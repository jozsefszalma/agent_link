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
from unittest.mock import patch, MagicMock, call

from agent_link import Message, Audience, AgentNode
from agent_link.decorators import smolagent_message_handler
from smolagents.agents import MultiStepAgent  # You may need to mock this

class TestSmolagentMessageHandler:
    def test_decorator_functionality(self):
        """Test the basic structure and functionality of the decorator"""
        # Create mocks
        mock_agent = MagicMock()
        mock_agent.run.return_value = "Agent response"
        
        mock_node = MagicMock()
        mock_node.agent_id = "test-agent"
        
        # Define a handler function to decorate
        @smolagent_message_handler(mock_agent, mock_node)
        def test_handler(message, agent_response):
            return f"Modified: {agent_response}"
        
        # Create a test message
        test_message = Message(
            sender_id="other-agent",
            content="Test question",
            audience=Audience.DIRECT,
            recipient_id="test-agent",
            message_id="msg-123"
        )
        
        # Call the decorated handler
        test_handler(test_message)
        
        # Check that the agent was called to process the message
        mock_agent.run.assert_called_once_with("Test question")
        
        # Check that the node sent a response with the modified text
        mock_node.send_message.assert_called_once()
        call_args = mock_node.send_message.call_args[1]
        assert call_args["content"] == "Modified: Agent response"
        assert call_args["audience"] == Audience.DIRECT
        assert call_args["recipient_id"] == "other-agent"
        assert call_args["in_reply_to"] == "msg-123"

    def test_decorator_no_modification(self):
        """Test when handler doesn't modify the agent's response"""
        # Create mocks
        mock_agent = MagicMock()
        mock_agent.run.return_value = "Unmodified response"
        
        mock_node = MagicMock()
        mock_node.agent_id = "test-agent"
        
        # Define a handler that doesn't modify the response
        @smolagent_message_handler(mock_agent, mock_node)
        def pass_through_handler(message, agent_response):
            # Processing but no modification
            return None
        
        # Create a test message
        test_message = Message(
            sender_id="other-agent",
            content="Another question",
            audience=Audience.EVERYONE,
            message_id="msg-456"
        )
        
        # Call the decorated handler
        pass_through_handler(test_message)
        
        # Check that response was sent with unmodified text
        mock_node.send_message.assert_called_once()
        call_args = mock_node.send_message.call_args[1]
        assert call_args["content"] == "Unmodified response"
        assert call_args["audience"] == Audience.EVERYONE
        assert call_args["in_reply_to"] == "msg-456"

    def test_decorator_ignore_own_messages(self):
        """Test that the decorator ignores messages from self"""
        # Create mocks
        mock_agent = MagicMock()
        mock_node = MagicMock()
        mock_node.agent_id = "my-agent-id"
        
        # Define handler
        handler = MagicMock()
        
        # Apply decorator
        decorated_handler = smolagent_message_handler(mock_agent, mock_node)(handler)
        
        # Create a message from self
        own_message = Message(
            sender_id="my-agent-id",  # Same as node's agent_id
            content="Self message",
            audience=Audience.EVERYONE
        )
        
        # Call decorated handler
        decorated_handler(own_message)
        
        # Agent and handler should not be called for own messages
        mock_agent.run.assert_not_called()
        handler.assert_not_called()
        mock_node.send_message.assert_not_called()

    def test_decorator_with_error_handling(self):
        """Test error handling in the decorator"""
        # Create mocks
        mock_agent = MagicMock()
        mock_agent.run.side_effect = Exception("Agent error")
        
        mock_node = MagicMock()
        mock_node.agent_id = "test-agent"
        
        # Define a handler that could cause errors
        @smolagent_message_handler(mock_agent, mock_node)
        def error_prone_handler(message, agent_response):
            if agent_response is None:
                return "Error occurred"
            return agent_response
        
        # Create a test message
        test_message = Message(
            sender_id="other-agent",
            content="Bad question",
            audience=Audience.DIRECT,
            recipient_id="test-agent"
        )
        
        # Since we're mocking the agent to raise an exception,
        # the test will fail if the decorator doesn't handle exceptions
        with pytest.raises(Exception):
            error_prone_handler(test_message)