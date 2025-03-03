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
import time
import uuid
from unittest.mock import MagicMock

from agent_link import AgentNode, Audience, Message
from agent_link.decorators import smolagent_message_handler

from tests.conftest import wait_for_condition

# Skip if smolagents not installed
try:
    from smolagents.agents import MultiStepAgent
    SMOLAGENTS_AVAILABLE = True
except ImportError:
    SMOLAGENTS_AVAILABLE = False

@pytest.mark.integration
@pytest.mark.need_mqtt_broker
@pytest.mark.skipif(not SMOLAGENTS_AVAILABLE, reason="smolagents package not installed")
class TestSmolagentIntegration:
    @pytest.mark.need_mqtt_broker
    def test_smolagent_decorator(self, real_mqtt_config, unique_room_id):
        """Test integrating smolagent with AgentNode via decorator"""
        # Create a mock agent since we may not want to use a real one for tests
        mock_agent = MagicMock()
        mock_agent.run.return_value = "This is a test response"
        
        # Create agent and client nodes
        agent_id = f"agent-{uuid.uuid4()}"
        client_id = f"client-{uuid.uuid4()}"
        
        agent_node = AgentNode(real_mqtt_config, room_id=unique_room_id, agent_id=agent_id)
        client_node = AgentNode(real_mqtt_config, room_id=unique_room_id, agent_id=client_id)
        
        # Track interactions
        agent_invoked = False
        agent_responded = False
        client_received = []
        
        # Create handler with the decorator
        @smolagent_message_handler(mock_agent, agent_node)
        def agent_handler(message, agent_response):
            nonlocal agent_invoked
            agent_invoked = True
            return f"Decorated: {agent_response}"
        
        # Client handler to track responses
        def client_handler(message):
            client_received.append(message)
            return None
        
        try:
            # Join and register handlers
            agent_node.join()
            agent_node.add_message_handler(agent_handler)
            
            client_node.join()
            client_node.add_message_handler(client_handler)
            
            # Wait for connections
            time.sleep(1)
            
            # Send query from client to agent
            query = "Can you help me with a test?"
            client_node.send_message(
                content=query,
                audience=Audience.DIRECT,
                recipient_id=agent_id
            )
            
            # Wait for response
            def response_received():
                return len(client_received) > 0
            
            assert wait_for_condition(response_received, timeout=5)
            
            # Verify agent was invoked
            assert agent_invoked is True
            mock_agent.run.assert_called_once_with(query)
            
            # Verify client received response
            assert len(client_received) == 1
            response = client_received[0]
            assert response.sender_id == agent_id
            assert "Decorated: This is a test response" in response.content
            
        finally:
            agent_node.leave()
            client_node.leave()
    
    @pytest.mark.need_mqtt_broker
    @pytest.mark.skipif(True, reason="Requires actual LLM - enable manually for testing")
    def test_with_real_smolagent(self, real_mqtt_config, unique_room_id):
        """Test with a real smolagent (disabled by default to avoid LLM costs)"""
        # Create a real (but minimal) agent
        # You might need to implement a minimal agent for this test
        from smolagents.agents import SimpleAgent
        from smolagents import HfApiModel  # or whatever model provider you use
        
        model = HfApiModel()  # This might need configuration
        agent = SimpleAgent(model=model)
        
        # Create agent and client nodes
        agent_id = f"real-agent-{uuid.uuid4()}"
        client_id = f"real-client-{uuid.uuid4()}"
        
        agent_node = AgentNode(real_mqtt_config, room_id=unique_room_id, agent_id=agent_id)
        client_node = AgentNode(real_mqtt_config, room_id=unique_room_id, agent_id=client_id)
        
        # Track received responses
        client_received = []
        
        # Create handler with the decorator
        @smolagent_message_handler(agent, agent_node)
        def agent_handler(message, agent_response):
            return agent_response
        
        # Client handler
        def client_handler(message):
            client_received.append(message)
            return None
        
        try:
            # Join and register handlers
            agent_node.join()
            agent_node.add_message_handler(agent_handler)
            
            client_node.join()
            client_node.add_message_handler(client_handler)
            
            # Wait for connections
            time.sleep(1)
            
            # Send a simple query that won't be expensive to process
            query = "What is 2+2?"
            client_node.send_message(
                content=query,
                audience=Audience.DIRECT,
                recipient_id=agent_id
            )
            
            # Wait for response with longer timeout for LLM processing
            def response_received():
                return len(client_received) > 0
            
            assert wait_for_condition(response_received, timeout=30)
            
            # Verify client received a response
            assert len(client_received) == 1
            response = client_received[0]
            assert response.sender_id == agent_id
            # Don't assert specific content since it depends on the LLM
            
        finally:
            agent_node.leave()
            client_node.leave()