"""Unit tests for the A2A helpers."""

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

from agent_link.a2a import (
    A2AEnvelope,
    A2AMessage,
    MessageSendConfiguration,
    create_send_message_request,
    create_send_message_result,
    create_text_message,
    create_text_part,
    derive_sender_id_from_message,
    parse_a2a_envelope,
)


def test_create_text_message_includes_metadata():
    message = create_text_message(
        "Hello",
        role="user",
        metadata={"sender_id": "tester"},
        extensions=["ext"],
        reference_task_ids=["task-1"],
        task_id="task-1",
        context_id="ctx-1",
    )

    payload = message.to_dict()
    assert payload["metadata"]["sender_id"] == "tester"
    assert payload["extensions"] == ["ext"]
    assert payload["referenceTaskIds"] == ["task-1"]
    assert payload["taskId"] == "task-1"
    assert payload["contextId"] == "ctx-1"
    assert message.primary_text == "Hello"


def test_create_send_message_request_structure():
    message = create_text_message("Hello", role="user")
    configuration = MessageSendConfiguration(history_length=5, blocking=True)
    request = create_send_message_request(
        message,
        request_id="req-1",
        configuration=configuration,
        metadata={"trace_id": "trace"},
    )

    payload = request.to_dict()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "req-1"
    assert payload["method"] == "message/send"
    assert payload["params"]["configuration"]["historyLength"] == 5
    assert payload["params"]["metadata"]["trace_id"] == "trace"


def test_parse_a2a_envelope_round_trip():
    original_message = create_text_message("Ping", role="user", metadata={"sender_id": "peer"})
    request = create_send_message_request(original_message, request_id="req-2")
    envelope = parse_a2a_envelope(request.to_dict())

    assert isinstance(envelope, A2AEnvelope)
    assert envelope.message is not None
    assert envelope.message.primary_text == "Ping"
    assert derive_sender_id_from_message(envelope.message) == "peer"


def test_create_send_message_result_preserves_request_id():
    message = create_text_message("Pong", role="agent", metadata={"senderId": "agent"})
    response = create_send_message_result(message, request_id="req-3")

    payload = response.to_dict()
    assert payload["jsonrpc"] == "2.0"
    assert payload["id"] == "req-3"
    assert payload["result"]["messageId"] == message.message_id
    assert payload["result"]["metadata"]["senderId"] == "agent"


def test_derive_sender_id_fallbacks():
    message = A2AMessage(
        role="agent",
        parts=[create_text_part("content")],
        message_id="msg-1",
    )

    assert derive_sender_id_from_message(message) == "a2a:agent"

    message = message.with_updates(metadata={"senderId": "Agent-42"})
    assert derive_sender_id_from_message(message) == "Agent-42"
