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


import json
import pytest
from unittest.mock import patch, MagicMock, call

from agent_link import AgentLink, ConnectionConfig, AuthMethod, QoSLevel
import paho.mqtt.client as mqtt

class TestAgentLink:
    def test_init(self, test_config):
        """Test initializing AgentLink"""
        with patch('paho.mqtt.client.Client') as mock_client:
            agent_link = AgentLink(test_config)
            
            # Check client creation
            mock_client.assert_called_once()
            # Check callback registration
            assert agent_link.client.on_connect is not None
            assert agent_link.client.on_disconnect is not None
            assert agent_link.client.on_message is not None
            assert agent_link.client.on_publish is not None
            assert agent_link.client.on_subscribe is not None

    def test_setup_auth_userpass(self, test_config):
        """Test setting up username/password auth"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            test_config.auth_method = AuthMethod.USERPASS
            test_config.username = "user"
            test_config.password = "pass"
            
            AgentLink(test_config)
            
            instance.username_pw_set.assert_called_once_with("user", "pass")

    def test_setup_auth_token(self, test_config):
        """Test setting up token auth"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            test_config.auth_method = AuthMethod.TOKEN
            test_config.token = "my-token"
            
            AgentLink(test_config)
            
            instance.username_pw_set.assert_called_once_with(
                username="token", password="my-token")

    def test_setup_auth_api_key(self, test_config):
        """Test setting up API key auth"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            test_config.auth_method = AuthMethod.API_KEY
            test_config.api_key = "my-api-key"
            
            AgentLink(test_config)
            
            instance.username_pw_set.assert_called_once_with(
                username="apikey", password="my-api-key")

    def test_setup_tls(self, test_config):
        """Test setting up TLS"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            test_config.use_tls = True
            test_config.cert_path = "/path/to/cert.pem"
            test_config.key_path = "/path/to/key.pem"
            
            AgentLink(test_config)
            
            instance.tls_set.assert_called_once_with(
                ca_certs=None,
                certfile="/path/to/cert.pem",
                keyfile="/path/to/key.pem"
            )

    def test_connect(self, test_config):
        """Test connecting to broker"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            agent_link = AgentLink(test_config)
            
            # Simulate successful connection
            def set_connected(*args, **kwargs):
                agent_link.connected = True
            
            instance.connect.side_effect = set_connected
            
            result = agent_link.connect()
            
            assert result is True
            instance.connect.assert_called_once_with(
                host=test_config.broker,
                port=test_config.port,
                keepalive=test_config.keep_alive
            )
            instance.loop_start.assert_called_once()

    def test_connect_error(self, test_config):
        """Test connect handling errors"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            agent_link = AgentLink(test_config)
            
            # Simulate connection failure
            instance.connect.side_effect = ConnectionRefusedError("Connection refused")
            
            with pytest.raises(ConnectionError):
                agent_link.connect()
            
            instance.loop_stop.assert_called_once()
            assert agent_link.connecting is False
            assert agent_link.connected is False

    def test_disconnect(self, test_config):
        """Test disconnecting from broker"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            agent_link.disconnect()
            
            instance.disconnect.assert_called_once()
            instance.loop_stop.assert_called_once()
            
            # Test disconnecting when not connected
            agent_link.connected = False
            agent_link.disconnect()
            # Should not call disconnect again
            assert instance.disconnect.call_count == 1

    def test_publish_dict(self, test_config):
        """Test publishing a dict message"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            # Configure mock
            publish_result = MagicMock()
            publish_result.is_published.return_value = True
            publish_result.mid = 123
            instance.publish.return_value = publish_result
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            payload = {"key": "value"}
            topic = "test/topic"
            
            message_id = agent_link.publish(
                topic=topic,
                payload=payload,
                qos=QoSLevel.AT_LEAST_ONCE
            )
            
            # Check result
            assert message_id == 123
            
            # Verify publish was called with JSON-encoded payload
            instance.publish.assert_called_once()
            call_args = instance.publish.call_args[1]
            assert call_args["topic"] == topic
            assert call_args["qos"] == 1
            assert json.loads(call_args["payload"]) == payload
            assert call_args["retain"] is False

    def test_publish_string(self, test_config):
        """Test publishing a string message"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            # Configure mock
            publish_result = MagicMock()
            publish_result.is_published.return_value = True
            publish_result.mid = 123
            instance.publish.return_value = publish_result
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            payload = "Hello, world!"
            topic = "test/topic"
            
            message_id = agent_link.publish(
                topic=topic,
                payload=payload,
                qos=QoSLevel.EXACTLY_ONCE,
                retain=True
            )
            
            # Check result
            assert message_id == 123
            
            # Verify publish was called with string payload
            instance.publish.assert_called_once()
            call_args = instance.publish.call_args[1]
            assert call_args["topic"] == topic
            assert call_args["payload"] == payload
            assert call_args["qos"] == 2
            assert call_args["retain"] is True

    def test_publish_not_connected(self, test_config):
        """Test publishing when not connected"""
        with patch('paho.mqtt.client.Client'):
            agent_link = AgentLink(test_config)
            agent_link.connected = False
            
            with pytest.raises(ConnectionError):
                agent_link.publish("test/topic", "message")

    def test_subscribe(self, test_config):
        """Test subscribing to a topic"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            # Configure mock
            instance.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            callback = lambda topic, payload: None
            topic = "test/topic"
            
            result = agent_link.subscribe(
                topic=topic,
                callback=callback,
                qos=QoSLevel.AT_LEAST_ONCE
            )
            
            # Check result
            assert result is True
            
            # Verify subscribe was called
            instance.subscribe.assert_called_once_with(topic, 1)
            
            # Verify callback was registered
            assert topic in agent_link._subscriptions
            assert callback in agent_link._subscriptions[topic]

    def test_subscribe_error(self, test_config):
        """Test handling subscribe errors"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            # Configure mock to return error
            instance.subscribe.return_value = (mqtt.MQTT_ERR_NO_CONN, 0)
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            result = agent_link.subscribe(
                topic="test/topic",
                callback=lambda topic, payload: None
            )
            
            # Should return False on error
            assert result is False

    def test_unsubscribe(self, test_config):
        """Test unsubscribing from a topic"""
        with patch('paho.mqtt.client.Client') as mock_client:
            instance = mock_client.return_value
            
            # Configure mock
            instance.unsubscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 1)
            
            agent_link = AgentLink(test_config)
            agent_link.connected = True
            
            # Register a callback first
            topic = "test/topic"
            callback = lambda topic, payload: None
            agent_link._subscriptions[topic] = [callback]
            
            result = agent_link.unsubscribe(topic)
            
            # Check result
            assert result is True
            
            # Verify unsubscribe was called
            instance.unsubscribe.assert_called_once_with(topic)
            
            # Verify callback was unregistered
            assert topic not in agent_link._subscriptions

    def test_topic_matches(self, test_config):
        """Test topic matching logic"""
        with patch('paho.mqtt.client.Client'):
            agent_link = AgentLink(test_config)
            
            # Exact match
            assert agent_link._topic_matches("test/topic", "test/topic") is True
            
            # Single-level wildcard
            assert agent_link._topic_matches("test/+/end", "test/middle/end") is True
            assert agent_link._topic_matches("test/+/end", "test/end") is False
            
            # Multi-level wildcard
            assert agent_link._topic_matches("test/#", "test/a/b/c") is True
            assert agent_link._topic_matches("test/#", "testing") is False
            
            # Combined wildcards
            assert agent_link._topic_matches("test/+/#", "test/a/b/c") is True
            assert agent_link._topic_matches("test/+/#", "test2/a/b/c") is False
            
            # Invalid wildcards (# not at end)
            assert agent_link._topic_matches("test/#/more", "test/a/more") is False

    def test_on_message(self, test_config):
        """Test message handling"""
        with patch('paho.mqtt.client.Client'):
            agent_link = AgentLink(test_config)
            
            # Create a mock callback
            callback = MagicMock()
            
            # Register callback
            topic = "test/topic"
            agent_link._subscriptions[topic] = [callback]
            
            # Create mock message
            message = MagicMock()
            message.topic = topic
            message.payload = json.dumps({"key": "value"}).encode('utf-8')
            
            # Call on_message
            agent_link._on_message(None, None, message)
            
            # Verify callback was called with correct args
            callback.assert_called_once()
            assert callback.call_args[0][0] == topic
            assert callback.call_args[0][1] == {"key": "value"}
            
            # Test wildcard subscription
            callback.reset_mock()
            agent_link._subscriptions.clear()
            agent_link._subscriptions["test/#"] = [callback]
            
            message.topic = "test/subtopic"
            agent_link._on_message(None, None, message)
            
            callback.assert_called_once()