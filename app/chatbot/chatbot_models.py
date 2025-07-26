import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Generator

from pydantic import BaseModel, ConfigDict, Field

from app.common.models import Role, StreamStep
from app.conversation.messages.message_models import AgentVersion


class ActionResult(BaseModel):
    """
    Represents the result of an action taken by the agent.
    """

    timestamp: datetime = Field(default=datetime.now(timezone.utc))
    thought: str
    action: str
    result: str

    def __str__(self) -> str:
        return f"""
        Thought: {self.thought}
        Action: {self.action}
        Result: {self.result}
    """


class Action(BaseModel):
    """
    Performs the action and returns the output of that action
    """

    name: str = Field(default="", description="Name of the action to choose")
    description: str = Field(default="", description="Explanation of what this action do")
    params: dict[str, Any] = Field(default={}, description="Input parameters for the action (if any)")


class AgentThought(BaseModel):
    """
    Represents the thought process of the agent.
    """

    thought: str = Field(default="", description="Reason behind the action taken")
    action: Action = Field(description="Action associated with this thought")

    def __str__(self) -> str:
        return self.model_dump_json()


class StreamChunk(BaseModel):
    """Represents a chunk of streamed data."""

    content: str
    step: StreamStep
    step_title: str


class AgentMessage(BaseModel):
    message: str
    role: Role
    timestamp: datetime = Field(default=datetime.now(timezone.utc))

    def get_formatted_prompt(self) -> str:
        ts_str = self.timestamp.strftime("%Y-%m-%d %H:%M")
        role_cap = self.role.value.capitalize()
        return f"[{role_cap}  - {ts_str}]  {self.message}"


class Phase(Enum):
    NEED_FINAL = "need_final"
    NEED_TOOL = "need_tool"


class AgentState(BaseModel):
    """State for the chat agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    messages: list[AgentMessage]
    user_message: str
    agent_message: str = Field(default="")
    prompt: str = Field(default="")

    # Multi-step reasoning fields
    phase: Phase = Field(default=Phase.NEED_FINAL)
    analysis: str = Field(default="")
    thought: AgentThought | None = Field(default=None)
    observations: list[ActionResult] = Field(default=[])

    reasoning: str = Field(default="")
    synthesis: str = Field(default="")

    # Quality assurance fields
    draft_response: str = Field(default="")
    evaluation: str = Field(default="")
    needs_refinement: bool = Field(default=True)
    refinement_count: int = Field(default=0)

    # Error handling
    retry: int = Field(default=0)
    error_message: str | None = Field(default=None)

    stream_queue: asyncio.Queue = Field(default_factory=lambda: asyncio.Queue(maxsize=0))

    def build_conversation_history(self, limit: int = 20) -> str:
        """Build the conversation history from the state."""
        self.messages.sort(key=lambda msg: msg.timestamp)
        return "\n".join(msg.get_formatted_prompt() for msg in self.messages[-limit:])

    def build_observation(self, limit: int = 5) -> str:
        """Build the observation from the state."""
        if not self.observations:
            return ""
        n = len(self.observations)
        observations = self.observations[-limit:] if n > 3 else self.observations
        prompt = "\n# OBSERVATIONS\n\n"
        prompt += "Below are the observations/result of your previous actions:\n"
        for idx, obs in enumerate(observations):
            prompt += f"## Observation {(idx + 1)}.\n"
            prompt += f"{obs}\n\n"
        return prompt

    def get_error_message(self) -> Generator[str, None, None]:
        if not self.error_message:
            yield ""
        else:
            yield f"Got error: {self.error_message}"
            self.error_message = None


# Requests
class AgentRequest(BaseModel):
    """
    Represents a request to an agent.
    """

    message_history: list[AgentMessage]
    message: str
    version: AgentVersion = Field(default=AgentVersion.KRISHNA_MINI)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# Responses
class AgentResponse(BaseModel):
    """
    Represents a response from an agent.
    """

    response: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AgentStreamResponse(BaseModel):
    """
    Represents a streamed response from an agent.
    """

    content: str
    step: StreamStep
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def stream_response(self) -> str:
        """
        Returns a string representation of the request for streaming.
        This method is used to format the request for streaming responses.
        """
        return f"data: {self.model_dump_json()}\n\n"


class AgentMessageSummary(BaseModel):
    """Represents a title and summary for the given messages"""

    title: str
    summary: str
