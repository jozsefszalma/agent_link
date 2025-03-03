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
from enum import Enum
from dataclasses import dataclass
from typing import Optional

class AuthMethod(Enum):
    """Authentication methods supported by the MQTT client."""
    NONE = "none"
    USERPASS = "userpass"
    TOKEN = "token"
    CERT = "cert"
    API_KEY = "api_key"


class QoSLevel(Enum):
    """Quality of Service levels for MQTT publishing and subscribing."""
    AT_MOST_ONCE = 0  # Fire and forget
    AT_LEAST_ONCE = 1  # Guaranteed delivery but duplicates possible
    EXACTLY_ONCE = 2  # Guaranteed delivery exactly once, highest overhead


@dataclass
class ConnectionConfig:
    """Configuration for MQTT broker connection."""
    broker: str
    port: int = 1883
    use_tls: bool = False
    auth_method: AuthMethod = AuthMethod.NONE
    username: Optional[str] = None
    password: Optional[str] = None
    token: Optional[str] = None
    cert_path: Optional[str] = None
    key_path: Optional[str] = None
    api_key: Optional[str] = None
    client_id: Optional[str] = None
    clean_session: bool = True
    keep_alive: int = 60

    def __post_init__(self):
        """Generate a client ID if not provided."""
        if not self.client_id:
            self.client_id = f"{uuid.uuid4()}" 