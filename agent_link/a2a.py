"""Utilities for working with the Agent-to-Agent (A2A) protocol."""
from __future__ import annotations

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

import uuid
from dataclasses import dataclass, field, replace
from typing import Any, Dict, List, Optional, Sequence, Union

from typing_extensions import Literal

A2ARole = Literal["user", "agent"]
JSONRPC_VERSION = "2.0"


@dataclass
class A2APart:
    """Represents a part of an A2A message."""

    kind: str
    data: Dict[str, Any] = field(default_factory=dict)
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        part: Dict[str, Any] = {"kind": self.kind, **self.data}
        if self.metadata:
            part["metadata"] = self.metadata
        return part

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "A2APart":
        if not isinstance(value, dict):  # pragma: no cover - defensive
            raise ValueError("A2A part must be a dictionary")
        kind = value.get("kind")
        if not isinstance(kind, str):
            raise ValueError("A2A part requires a string 'kind' field")
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else None
        payload = {k: v for k, v in value.items() if k not in {"kind", "metadata"}}
        return cls(kind=kind, data=payload, metadata=metadata)

    @property
    def text(self) -> Optional[str]:
        value = self.data.get("text")
        return value if isinstance(value, str) else None


def create_text_part(text: str, metadata: Optional[Dict[str, Any]] = None) -> A2APart:
    """Create a text part for a message."""

    return A2APart(kind="text", data={"text": text}, metadata=metadata)


@dataclass
class A2AMessage:
    """Representation of an A2A message."""

    role: A2ARole
    parts: List[A2APart]
    message_id: str
    kind: str = "message"
    metadata: Optional[Dict[str, Any]] = None
    extensions: Optional[List[str]] = None
    reference_task_ids: Optional[List[str]] = None
    task_id: Optional[str] = None
    context_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "role": self.role,
            "parts": [part.to_dict() for part in self.parts],
            "messageId": self.message_id,
            "kind": self.kind,
        }
        if self.metadata:
            payload["metadata"] = self.metadata
        if self.extensions:
            payload["extensions"] = list(self.extensions)
        if self.reference_task_ids:
            payload["referenceTaskIds"] = list(self.reference_task_ids)
        if self.task_id:
            payload["taskId"] = self.task_id
        if self.context_id:
            payload["contextId"] = self.context_id
        return payload

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "A2AMessage":
        if not isinstance(value, dict):
            raise ValueError("A2A message must be a dictionary")
        role = value.get("role")
        if role not in ("user", "agent"):
            raise ValueError("A2A message role must be 'user' or 'agent'")
        parts_value = value.get("parts")
        if not isinstance(parts_value, list) or not parts_value:
            raise ValueError("A2A message requires a non-empty 'parts' list")
        parts = [A2APart.from_dict(part) for part in parts_value]
        message_id = value.get("messageId") or value.get("message_id")
        if not isinstance(message_id, str):
            raise ValueError("A2A message requires a string 'messageId'")
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else None
        extensions = value.get("extensions") if isinstance(value.get("extensions"), list) else None
        reference_task_ids = (
            value.get("referenceTaskIds")
            if isinstance(value.get("referenceTaskIds"), list)
            else None
        )
        task_id = value.get("taskId") or value.get("task_id")
        context_id = value.get("contextId") or value.get("context_id")
        kind = value.get("kind", "message")
        return cls(
            role=role,
            parts=parts,
            message_id=message_id,
            kind=kind,
            metadata=metadata,
            extensions=list(extensions) if extensions else None,
            reference_task_ids=list(reference_task_ids) if reference_task_ids else None,
            task_id=task_id if isinstance(task_id, str) else None,
            context_id=context_id if isinstance(context_id, str) else None,
        )

    @property
    def primary_text(self) -> Optional[str]:
        """Return the first text part in the message, if present."""

        for part in self.parts:
            text = part.text
            if text is not None:
                return text
        return None

    def with_updates(self, **updates: Any) -> "A2AMessage":
        """Return a copy of the message with the provided updates."""

        return replace(self, **updates)


@dataclass
class MessageSendConfiguration:
    """Configuration options for message sending."""

    accepted_output_modes: Optional[List[str]] = None
    history_length: Optional[int] = None
    push_notification_config: Optional[Dict[str, Any]] = None
    blocking: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if self.accepted_output_modes:
            payload["acceptedOutputModes"] = list(self.accepted_output_modes)
        if self.history_length is not None:
            payload["historyLength"] = self.history_length
        if self.push_notification_config:
            payload["pushNotificationConfig"] = self.push_notification_config
        if self.blocking is not None:
            payload["blocking"] = self.blocking
        return payload

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "MessageSendConfiguration":
        if not isinstance(value, dict):
            raise ValueError("Configuration must be a dictionary")
        accepted_output_modes = (
            list(value.get("acceptedOutputModes"))
            if isinstance(value.get("acceptedOutputModes"), list)
            else None
        )
        history_length = value.get("historyLength")
        if history_length is not None and not isinstance(history_length, int):
            raise ValueError("'historyLength' must be an integer if provided")
        push_notification_config = (
            value.get("pushNotificationConfig")
            if isinstance(value.get("pushNotificationConfig"), dict)
            else None
        )
        blocking = value.get("blocking")
        if blocking is not None and not isinstance(blocking, bool):
            raise ValueError("'blocking' must be a boolean if provided")
        return cls(
            accepted_output_modes=accepted_output_modes,
            history_length=history_length,
            push_notification_config=push_notification_config,
            blocking=blocking,
        )


@dataclass
class MessageSendParams:
    """Parameters for the ``message/send`` JSON-RPC call."""

    message: A2AMessage
    configuration: Optional[MessageSendConfiguration] = None
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"message": self.message.to_dict()}
        if self.configuration:
            payload["configuration"] = self.configuration.to_dict()
        if self.metadata:
            payload["metadata"] = self.metadata
        return payload

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "MessageSendParams":
        if not isinstance(value, dict):
            raise ValueError("Parameters must be a dictionary")
        message_value = value.get("message")
        if not isinstance(message_value, dict):
            raise ValueError("Parameters must include a 'message' dictionary")
        message = A2AMessage.from_dict(message_value)
        configuration_value = value.get("configuration")
        configuration = (
            MessageSendConfiguration.from_dict(configuration_value)
            if isinstance(configuration_value, dict)
            else None
        )
        metadata = value.get("metadata") if isinstance(value.get("metadata"), dict) else None
        return cls(message=message, configuration=configuration, metadata=metadata)


@dataclass
class SendMessageRequest:
    """A JSON-RPC request envelope for ``message/send``."""

    id: Union[str, int]
    params: MessageSendParams
    method: str = "message/send"
    jsonrpc: str = JSONRPC_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "jsonrpc": self.jsonrpc,
            "id": self.id,
            "method": self.method,
            "params": self.params.to_dict(),
        }


@dataclass
class A2AEnvelope:
    """General JSON-RPC envelope used by the A2A protocol."""

    jsonrpc: str
    id: Optional[Union[str, int]]
    method: Optional[str] = None
    params: Optional[MessageSendParams] = None
    result: Any = None
    error: Optional[Dict[str, Any]] = None
    raw: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_request(self) -> bool:
        return self.method is not None

    @property
    def message(self) -> Optional[A2AMessage]:
        if self.params:
            return self.params.message
        if isinstance(self.result, dict):
            try:
                return A2AMessage.from_dict(self.result)
            except ValueError:  # pragma: no cover - defensive guard for incompatible results
                return None
        return None

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"jsonrpc": self.jsonrpc}
        if self.id is not None:
            payload["id"] = self.id
        if self.method:
            payload["method"] = self.method
        if self.params:
            payload["params"] = self.params.to_dict()
        if self.result is not None:
            payload["result"] = self.result
        if self.error is not None:
            payload["error"] = self.error
        return payload

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "A2AEnvelope":
        if not isinstance(value, dict):
            raise ValueError("Envelope must be a dictionary")
        jsonrpc_value = value.get("jsonrpc")
        if jsonrpc_value != JSONRPC_VERSION:
            raise ValueError("Unsupported or missing JSON-RPC version")
        params_value = value.get("params")
        params = None
        if isinstance(params_value, dict):
            try:
                params = MessageSendParams.from_dict(params_value)
            except ValueError:
                params = None
        return cls(
            jsonrpc=jsonrpc_value,
            id=value.get("id"),
            method=value.get("method"),
            params=params,
            result=value.get("result"),
            error=value.get("error") if isinstance(value.get("error"), dict) else None,
            raw=value,
        )


def create_text_message(
    text: str,
    *,
    role: A2ARole,
    message_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
    extensions: Optional[Sequence[str]] = None,
    reference_task_ids: Optional[Sequence[str]] = None,
    task_id: Optional[str] = None,
    context_id: Optional[str] = None,
) -> A2AMessage:
    """Convenience helper to build a text-only A2A message."""

    return A2AMessage(
        role=role,
        parts=[create_text_part(text)],
        message_id=message_id or str(uuid.uuid4()),
        metadata=metadata,
        extensions=list(extensions) if extensions else None,
        reference_task_ids=list(reference_task_ids) if reference_task_ids else None,
        task_id=task_id,
        context_id=context_id,
    )


def create_send_message_request(
    message: A2AMessage,
    *,
    request_id: Optional[Union[str, int]] = None,
    configuration: Optional[MessageSendConfiguration] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> SendMessageRequest:
    """Create a ``message/send`` request envelope."""

    params = MessageSendParams(message=message, configuration=configuration, metadata=metadata)
    return SendMessageRequest(id=request_id or str(uuid.uuid4()), params=params)


def is_a2a_envelope(payload: Any) -> bool:
    """Return True if the payload looks like an A2A JSON-RPC envelope."""

    if not isinstance(payload, dict):
        return False
    return payload.get("jsonrpc") == JSONRPC_VERSION


def parse_a2a_envelope(payload: Any) -> Optional[A2AEnvelope]:
    """Parse a JSON payload into an :class:`A2AEnvelope` if possible."""

    if not is_a2a_envelope(payload):
        return None
    try:
        return A2AEnvelope.from_dict(payload)
    except ValueError:
        return None


def derive_sender_id_from_message(message: A2AMessage) -> str:
    """Derive a sender identifier from an A2A message."""

    metadata = message.metadata or {}
    for key in ("sender_id", "senderId", "agent_id", "agentId", "authorId", "author_id"):
        value = metadata.get(key)
        if isinstance(value, str) and value.strip():
            return value
    if message.context_id:
        return message.context_id
    if message.task_id:
        return message.task_id
    return f"a2a:{message.role}"

