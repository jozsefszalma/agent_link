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


import logging
from typing import Callable, Any, Optional

from smolagents.agents import MultiStepAgent
from agent_link.node import AgentNode, Message, Audience

logger = logging.getLogger(__name__)

def smolagent_message_handler(
    agent: MultiStepAgent,
    node: AgentNode
) -> Callable[[Callable[[Message, Optional[str]], Optional[str]]], Callable[[Message], None]]:
    """
    Decorator integrating a smolagent (subclass of MultiStepAgent) with an AgentNode's
    message handling. 
    
    The returned decorator wraps a user-defined handler function that receives:
        - message (Message): The incoming MQTT message from agent_link.
        - agent_response (Optional[str]): The smolagent’s raw response.

    The user-defined handler can return:
        - A string to override the smolagent’s response (sent back to the sender).
        - None to keep the smolagent’s response unchanged.
    """
    def real_decorator(user_handler: Callable[[Message, Optional[str]], Optional[str]]):
        def wrapper(incoming_message: Message):
            # Don't respond to ourselves
            if incoming_message.sender_id == node.agent_id:
                return
            
            # Let the smolagent process the incoming content
            agent_response = agent.run(incoming_message.content)

            # Call the user's handler, which can optionally override the response
            overridden_response = user_handler(incoming_message, agent_response)
            final_response = overridden_response if overridden_response is not None else agent_response

            # Send the final response if we have one
            if final_response:
                node.send_message(
                    content=final_response,
                    audience=incoming_message.audience,
                    recipient_id=(
                        incoming_message.sender_id 
                        if incoming_message.audience == Audience.DIRECT 
                        else None
                    ),
                    in_reply_to=incoming_message.message_id
                )
        return wrapper
    return real_decorator
