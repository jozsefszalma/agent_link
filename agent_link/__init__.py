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


"""
AI Agent Communication Library using MQTT

This package provides tools for AI agent communication through 
MQTT brokers, enabling both group chats and direct messaging.
"""

from agent_link.config import ConnectionConfig, AuthMethod, QoSLevel
from agent_link.client import AgentLink
from agent_link.node import AgentNode, Audience, Message
from agent_link.decorators import smolagent_message_handler
from agent_link.a2a import (
    A2AEnvelope,
    A2AMessage,
    A2APart,
    A2ARole,
    MessageSendConfiguration,
    MessageSendParams,
    SendMessageRequest,
    create_send_message_request,
    create_text_message,
    create_text_part,
    derive_sender_id_from_message,
    is_a2a_envelope,
    parse_a2a_envelope,
)

__version__ = "0.1.0"
