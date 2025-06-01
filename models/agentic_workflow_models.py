from enum import Enum
from typing import Any, TypedDict


class AgentState(TypedDict):
    """State for the chat agent workflow."""

    messages: list[str]
    user_message: str
    agent_message: str
    scratchpad: str  # Optional scratchpad for intermediate thoughts or notes
    stream_queue: Any


class StreamStep(Enum):
    """Enum for different steps in the streaming process."""

    THIKING = "thinking"
    FINAL_RESPONSE = "final_response"


class StreamChunk(TypedDict):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep
