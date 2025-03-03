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
from agent_link import ConnectionConfig, AgentLink, QoSLevel, AuthMethod

@pytest.mark.integration
@pytest.mark.need_mqtt_broker
class TestMqttConnection:
    @pytest.mark.need_mqtt_broker
    def test_connect_disconnect(self, real_mqtt_config):
        """Test basic connection to a real MQTT broker"""
        agent_link = AgentLink(real_mqtt_config)
        
        try:
            # Connect
            connected = agent_link.connect()
            assert connected is True
            assert agent_link.connected is True
            
            # Disconnect
            agent_link.disconnect()
            assert agent_link.connected is False
            
        finally:
            # Ensure cleanup
            if agent_link.connected:
                agent_link.disconnect()
    
    @pytest.mark.need_mqtt_broker
    def test_context_manager(self, real_mqtt_config):
        """Test context manager protocol"""
        with AgentLink(real_mqtt_config) as agent_link:
            assert agent_link.connected is True
        
        # Should be disconnected after context exits
        assert agent_link.connected is False
    
    @pytest.mark.integration
    def test_connection_refused(self):
        """Test handling connection failure"""
        bad_config = ConnectionConfig(
            broker="non.existent.broker.example",
            port=1883,
            auth_method=AuthMethod.NONE
        )
        
        agent_link = AgentLink(bad_config)
        
        with pytest.raises(ConnectionError):
            agent_link.connect(timeout=2)