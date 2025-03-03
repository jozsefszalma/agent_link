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
import uuid
from agent_link import ConnectionConfig, AuthMethod, QoSLevel

class TestConnectionConfig:
    def test_init_with_defaults(self):
        """Test creating a ConnectionConfig with minimal parameters"""
        config = ConnectionConfig(broker="test.mosquitto.org")
        
        assert config.broker == "test.mosquitto.org"
        assert config.port == 1883
        assert config.use_tls is False
        assert config.auth_method == AuthMethod.NONE
        assert config.keep_alive == 60
        assert config.clean_session is True
        assert config.client_id is not None  # Should generate a UUID

    def test_init_with_custom_values(self):
        """Test creating a ConnectionConfig with custom parameters"""
        config = ConnectionConfig(
            broker="broker.hivemq.com",
            port=8883,
            use_tls=True,
            auth_method=AuthMethod.USERPASS,
            username="testuser",
            password="testpass",
            client_id="custom-client-123",
            keep_alive=30,
            clean_session=False
        )
        
        assert config.broker == "broker.hivemq.com"
        assert config.port == 8883
        assert config.use_tls is True
        assert config.auth_method == AuthMethod.USERPASS
        assert config.username == "testuser"
        assert config.password == "testpass"
        assert config.client_id == "custom-client-123"
        assert config.keep_alive == 30
        assert config.clean_session is False

    def test_client_id_generation(self):
        """Test that client_id is generated if not provided"""
        config1 = ConnectionConfig(broker="example.com")
        config2 = ConnectionConfig(broker="example.com")
        
        assert config1.client_id != config2.client_id
        # Verify it's a valid UUID string
        try:
            uuid.UUID(config1.client_id)
        except ValueError:
            pytest.fail("client_id is not a valid UUID")

    def test_auth_methods(self):
        """Test different authentication methods"""
        # API Key auth
        config = ConnectionConfig(
            broker="example.com",
            auth_method=AuthMethod.API_KEY,
            api_key="my-api-key"
        )
        assert config.auth_method == AuthMethod.API_KEY
        assert config.api_key == "my-api-key"
        
        # Token auth
        config = ConnectionConfig(
            broker="example.com",
            auth_method=AuthMethod.TOKEN,
            token="my-token"
        )
        assert config.auth_method == AuthMethod.TOKEN
        assert config.token == "my-token"
        
        # Certificate auth
        config = ConnectionConfig(
            broker="example.com",
            auth_method=AuthMethod.CERT,
            cert_path="/path/to/cert.pem",
            key_path="/path/to/key.pem"
        )
        assert config.auth_method == AuthMethod.CERT
        assert config.cert_path == "/path/to/cert.pem"
        assert config.key_path == "/path/to/key.pem"