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
import time
import json
import uuid
import logging
from typing import Any, Callable, Dict, List, Optional, Union

# 3rd party imports
import paho.mqtt.client as mqtt

# Package imports
from .config import ConnectionConfig, AuthMethod, QoSLevel

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class AgentLink:
    """
    MQTT Client for AI agent communication.
    
    This class provides a high-level interface for AI agents to communicate
    over MQTT, handling connection, authentication, publishing, and subscription.
    """
    
    def __init__(self, config: ConnectionConfig):
        """
        Initialize the MQTT client with the provided configuration.
        
        Args:
            config: Configuration for connecting to the MQTT broker
        """
        self.config = config
        
        # Create the MQTT client
        self.client = mqtt.Client(client_id=self.config.client_id, 
                                 clean_session=self.config.clean_session)
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        self.client.on_log = self._on_log
        
        # Message handling
        self._subscriptions: Dict[str, List[Callable]] = {}
        self._pending_messages: Dict[int, Dict[str, Any]] = {}
        self._last_message_id = 0
        
        # Connection status
        self.connected = False
        self.connecting = False
        
        # Configure TLS if needed
        if self.config.use_tls:
            self._setup_tls()
            
        # Configure authentication
        self._setup_auth()
    
    def _setup_tls(self) -> None:
        """Set up TLS/SSL for secure connection."""
        try:
            if self.config.cert_path and self.config.key_path:
                self.client.tls_set(
                    ca_certs=None,  # Can be set if needed
                    certfile=self.config.cert_path,
                    keyfile=self.config.key_path
                )
            else:
                # Standard TLS without cert authentication
                self.client.tls_set()
        except Exception as e:
            logger.error(f"Failed to set up TLS: {e}")
            raise
    
    def _setup_auth(self) -> None:
        """Set up authentication based on the configured method."""
        try:
            if self.config.auth_method == AuthMethod.USERPASS:
                if not self.config.username or not self.config.password:
                    raise ValueError("Username and password required for USERPASS authentication")
                self.client.username_pw_set(self.config.username, self.config.password)
                
            elif self.config.auth_method == AuthMethod.TOKEN:
                if not self.config.token:
                    raise ValueError("Token required for TOKEN authentication")
                self.client.username_pw_set(username="token", password=self.config.token)
                
            elif self.config.auth_method == AuthMethod.API_KEY:
                if not self.config.api_key:
                    raise ValueError("API key required for API_KEY authentication")
                self.client.username_pw_set(username="apikey", password=self.config.api_key)
                
            # CERT auth is handled in _setup_tls
        except Exception as e:
            logger.error(f"Authentication setup failed: {e}")
            raise
    
    def connect(self, timeout: int = 10) -> bool:
        """
        Connect to the MQTT broker.
        
        Args:
            timeout: Maximum time to wait for connection in seconds
            
        Returns:
            bool: True if connection successful, False otherwise
            
        Raises:
            ConnectionError: If connection fails
        """
        if self.connected:
            logger.info("Already connected to broker")
            return True
        
        if self.connecting:
            logger.info("Connection already in progress")
            return False
        
        self.connecting = True
        
        try:
            logger.info(f"Connecting to broker {self.config.broker}:{self.config.port}...")
            self.client.connect(
                host=self.config.broker,
                port=self.config.port,
                keepalive=self.config.keep_alive
            )
            
            # Start the network loop
            self.client.loop_start()
            
            # Wait for connection
            start_time = time.time()
            while not self.connected and time.time() - start_time < timeout:
                time.sleep(0.1)
                
            if not self.connected:
                self.client.loop_stop()
                self.connecting = False
                raise ConnectionError(f"Failed to connect to {self.config.broker} within timeout")
                
            logger.info(f"Successfully connected to {self.config.broker}")
            return True
            
        except Exception as e:
            self.client.loop_stop()
            logger.error(f"Connection failed: {e}")
            self.connecting = False
            raise ConnectionError(f"Failed to connect to MQTT broker: {e}")
        
    def disconnect(self) -> None:
        """
        Disconnect from the MQTT broker.
        """
        if self.connected:
            logger.info("Disconnecting from broker...")
            self.client.disconnect()
            self.client.loop_stop()
        else:
            logger.info("Not connected, no need to disconnect")
    
    def publish(self, 
                topic: str, 
                payload: Union[Dict[str, Any], str, bytes],
                qos: QoSLevel = QoSLevel.AT_LEAST_ONCE,
                retain: bool = False,
                timeout: int = 10) -> Optional[int]:
        """
        Publish a message to a topic.
        
        Args:
            topic: The topic to publish to
            payload: Message payload - can be a dict (auto-converted to JSON),
                     a string, or raw bytes
            qos: Quality of Service level
            retain: Whether the broker should retain this message
            timeout: Timeout in seconds for waiting for publication acknowledgment
            
        Returns:
            Optional[int]: Message ID if successful, None if failed
            
        Raises:
            ConnectionError: If not connected to broker
            ValueError: If invalid parameters are provided
            RuntimeError: If publishing fails
        """
        if not self.connected:
            raise ConnectionError("Not connected to MQTT broker")
        
        if not topic:
            raise ValueError("Topic cannot be empty")
        
        try:
            # Convert dict to JSON string
            if isinstance(payload, dict):
                payload = json.dumps(payload)
            
            # Track this message for acknowledgment if QoS > 0
            message_info = self.client.publish(
                topic=topic,
                payload=payload,
                qos=qos.value,
                retain=retain
            )
            
            if qos != QoSLevel.AT_MOST_ONCE:
                # Wait for message to be published
                start_time = time.time()
                while not message_info.is_published() and time.time() - start_time < timeout:
                    time.sleep(0.01)
                
                if not message_info.is_published():
                    logger.warning(f"Publication to {topic} not confirmed within timeout")
                    return None
            
            logger.debug(f"Published message to {topic} with ID {message_info.mid}")
            return message_info.mid
            
        except Exception as e:
            logger.error(f"Failed to publish to {topic}: {e}")
            raise RuntimeError(f"Failed to publish message: {e}")
    
    def subscribe(self, 
                 topic: str, 
                 callback: Callable[[str, Dict[str, Any]], None],
                 qos: QoSLevel = QoSLevel.AT_LEAST_ONCE) -> bool:
        """
        Subscribe to a topic and register a callback for received messages.
        
        Args:
            topic: The topic pattern to subscribe to (can include wildcards)
            callback: Function to call when a message is received
                     Should accept (topic, payload) where payload is parsed JSON if valid
            qos: Quality of Service level
            
        Returns:
            bool: True if subscription was successful, False otherwise
            
        Raises:
            ConnectionError: If not connected to broker
        """
        if not self.connected:
            raise ConnectionError("Not connected to MQTT broker")
        
        try:
            result, mid = self.client.subscribe(topic, qos.value)
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to subscribe to {topic}, error code: {result}")
                return False
            
            # Register the callback
            if topic not in self._subscriptions:
                self._subscriptions[topic] = []
            self._subscriptions[topic].append(callback)
            
            logger.info(f"Subscribed to {topic} with QoS {qos.value}")
            return True
            
        except Exception as e:
            logger.error(f"Subscribe error for {topic}: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """
        Unsubscribe from a topic.
        
        Args:
            topic: The topic to unsubscribe from
            
        Returns:
            bool: True if unsubscription was successful
            
        Raises:
            ConnectionError: If not connected to broker
        """
        if not self.connected:
            raise ConnectionError("Not connected to MQTT broker")
        
        try:
            result, mid = self.client.unsubscribe(topic)
            
            if result != mqtt.MQTT_ERR_SUCCESS:
                logger.error(f"Failed to unsubscribe from {topic}")
                return False
            
            # Remove callbacks
            if topic in self._subscriptions:
                del self._subscriptions[topic]
            
            logger.info(f"Unsubscribed from {topic}")
            return True
            
        except Exception as e:
            logger.error(f"Unsubscribe error for {topic}: {e}")
            return False
    
    def _on_connect(self, client, userdata, flags, rc: int) -> None:
        """Callback for when the client connects to the broker."""
        connection_codes = {
            0: "Connection successful",
            1: "Connection refused - incorrect protocol version",
            2: "Connection refused - invalid client identifier",
            3: "Connection refused - server unavailable",
            4: "Connection refused - bad username or password",
            5: "Connection refused - not authorized"
        }
        
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to broker: {connection_codes.get(rc, f'Unknown result code {rc}')}")
        else:
            self.connected = False
            logger.error(f"Connection failed: {connection_codes.get(rc, f'Unknown result code {rc}')}")
        
        self.connecting = False
    
    def _on_disconnect(self, client, userdata, rc: int) -> None:
        """Callback for when the client disconnects from the broker."""
        self.connected = False
        if rc == 0:
            logger.info("Cleanly disconnected from broker")
        else:
            logger.warning(f"Unexpected disconnect from broker, code: {rc}")
    
    def _on_message(self, client, userdata, msg) -> None:
        """Callback for when a message is received from the broker."""
        topic = msg.topic
        payload_bytes = msg.payload
        
        # Try to parse JSON, otherwise use the raw payload
        try:
            payload = json.loads(payload_bytes.decode('utf-8'))
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                payload = payload_bytes.decode('utf-8')
            except UnicodeDecodeError:
                # If it can't be decoded as utf-8, use raw bytes
                payload = payload_bytes
        
        logger.debug(f"Received message on {topic}")
        
        # Find matching subscriptions
        # First try exact match
        for sub_topic, callbacks in self._subscriptions.items():
            if self._topic_matches(sub_topic, topic):
                for callback in callbacks:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        logger.error(f"Error in callback for {topic}: {e}")
    
    def _topic_matches(self, subscription: str, topic: str) -> bool:
        """Check if a topic matches a subscription pattern."""
        # Split both by '/'
        sub_parts = subscription.split('/')
        topic_parts = topic.split('/')
        
        # Check if multi-level wildcard is present
        if '#' in sub_parts:
            # '#' must be the last character
            if sub_parts[-1] == '#':
                # Check if the prefix matches
                prefix_len = len(sub_parts) - 1
                return (len(topic_parts) >= prefix_len and
                        all(s == '+' or s == t 
                            for s, t in zip(sub_parts[:prefix_len], topic_parts[:prefix_len])))
            return False
        
        # No multi-level wildcard, must have same number of parts
        if len(sub_parts) != len(topic_parts):
            return False
        
        # Check each part
        return all(s == '+' or s == t for s, t in zip(sub_parts, topic_parts))
    
    def _on_publish(self, client, userdata, mid: int) -> None:
        """Callback for when a message is successfully published."""
        logger.debug(f"Message {mid} published successfully")
        
        # If we were tracking this message, update its status
        if mid in self._pending_messages:
            self._pending_messages[mid]['published'] = True
    
    def _on_subscribe(self, client, userdata, mid: int, granted_qos) -> None:
        """Callback for when a subscription is confirmed."""
        logger.debug(f"Subscription confirmed, mid: {mid}, QoS: {granted_qos}")
    
    def _on_log(self, client, userdata, level: int, buf: str) -> None:
        """Callback for client logging."""
        if level == mqtt.MQTT_LOG_DEBUG:
            logger.debug(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_INFO:
            logger.info(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_NOTICE:
            logger.info(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_WARNING:
            logger.warning(f"MQTT: {buf}")
        elif level == mqtt.MQTT_LOG_ERR:
            logger.error(f"MQTT: {buf}")
    
    def __enter__(self):
        """Support for context manager protocol."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Support for context manager protocol."""
        self.disconnect()