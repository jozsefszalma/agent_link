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
import pytest
import socket
import time
import threading
from typing import Dict, Any, Generator, List, Tuple
from unittest.mock import MagicMock, patch

import os
from dotenv import load_dotenv

# Get the directory containing this file (tests/) then go up one level
project_root = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..')
)

# Build an absolute path to .env in the root folder
env_path = os.path.join(project_root, '.env')

# Load it:
load_dotenv(dotenv_path=env_path)

import paho.mqtt.client as mqtt

from agent_link import ConnectionConfig, AuthMethod, QoSLevel, AgentLink, AgentNode, Audience, Message
from agent_link.decorators import smolagent_message_handler

# Replace or update in tests/conftest.py

# Create a more robust check if the broker is available
def is_mqtt_broker_available() -> bool:
    broker = os.getenv("MQTT_BROKER", "localhost")
    port = int(os.getenv("MQTT_PORT", "1883"))
    
    # First check if we're using a local or remote broker
    if broker in ["localhost", "127.0.0.1"]:
        try:
            socket.create_connection((broker, port), timeout=1)
            return True
        except (socket.timeout, ConnectionRefusedError, OSError):
            return False
    else:
        # For remote brokers, we'll assume they're available if credentials are provided
        if os.getenv("MQTT_USER") and os.getenv("MQTT_PASS"):
            return True
        return False

# Add a more descriptive marker for skipping
need_mqtt_broker = pytest.mark.skipif(
    not is_mqtt_broker_available(),
    reason="MQTT broker not available or credentials missing"
)

skip_integration = pytest.mark.skipif(
    os.getenv("SKIP_INTEGRATION_TESTS", "false").lower() in ("true", "1", "yes"),
    reason="Integration tests disabled via environment variable"
)

# Create a mock model for smolagents integration testing
class MockModel:
    def generate(self, prompt: str) -> str:
        return f"Response to: {prompt}"

# Create a mock agent for testing decorators
class MockAgent:
    def __init__(self):
        self.model = MockModel()
    
    def run(self, input_text: str) -> str:
        return f"Agent processed: {input_text}"

# Fixture for configuration with default test values
@pytest.fixture
def test_config() -> ConnectionConfig:
    connection_config = ConnectionConfig(
        broker=os.getenv("MQTT_BROKER", "localhost"),
        port=int(os.getenv("MQTT_PORT", "1883")),
        username=os.getenv("MQTT_USER"),
        password=os.getenv("MQTT_PASS"),
        use_tls = os.getenv("MQTT_USE_TLS", "true").lower() in ("true", "1", "yes"),
        auth_method=AuthMethod.USERPASS if os.getenv("MQTT_USER") else AuthMethod.NONE,
        client_id="test_client")
    print("CONNECTION: ", connection_config)
    return connection_config
    

# Fixture that mocks the mqtt.Client
@pytest.fixture
def mock_mqtt_client():
    with patch('paho.mqtt.client.Client') as mock_client:
        # Configure the mock to simulate connection success
        instance = mock_client.return_value
        instance.connect.return_value = 0
        instance.publish.return_value.is_published.return_value = True
        instance.publish.return_value.mid = 1
        instance.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        instance.unsubscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
        
        yield instance

# Fixture for a mocked AgentLink
@pytest.fixture
def mock_agent_link():
    with patch('agent_link.node.AgentLink') as mock_link:
        instance = mock_link.return_value
        instance.connect.return_value = True
        instance.publish.return_value = "message-id-123"
        instance.subscribe.return_value = True
        instance.unsubscribe.return_value = True
        instance.connected = True
        
        yield instance

# Fixture for integration tests that need a real MQTT broker
@pytest.fixture
def real_mqtt_config() -> ConnectionConfig:
    """Create connection config from environment variables"""
    return ConnectionConfig(
        broker=os.getenv("MQTT_BROKER", "localhost"),
        port=int(os.getenv("MQTT_PORT", "1883")),
        username=os.getenv("MQTT_USER"),
        password=os.getenv("MQTT_PASS"),
        use_tls=os.getenv("MQTT_USE_TLS", "false").lower() in ("true", "1", "yes"),
        auth_method=AuthMethod.USERPASS if os.getenv("MQTT_USER") else AuthMethod.NONE
    )

# Fixture to generate unique room IDs for testing
@pytest.fixture
def unique_room_id() -> str:
    import uuid
    return f"test_room_{uuid.uuid4()}"

# Fixture for message receipt tracking in integration tests
@pytest.fixture
def message_tracker() -> List[Dict[str, Any]]:
    return []

# Helper function to wait for a condition with timeout
def wait_for_condition(condition_func, timeout=10, interval=0.1):
    start_time = time.time()
    while time.time() - start_time < timeout:
        if condition_func():
            return True
        time.sleep(interval)
    return False