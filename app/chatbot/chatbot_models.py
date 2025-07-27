import os
import asyncio
from datetime import datetime, timezone
from enum import Enum
from typing import Any, ClassVar, Generator

from pydantic import BaseModel, ConfigDict, Field

from app.common.models import Role, StreamStep
from app.conversation.messages.message_models import AgentVersion
import shutil


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
        return f"""
## {role_cap} - {ts_str}
{self.message}
"""


class Phase(Enum):
    NEED_FINAL = "need_final"
    NEED_TOOL = "need_tool"


class MemoryManagementConfig(BaseModel):
    CONTEXT_LENGTH: ClassVar[int] = 100000
    SYSTEM_PROMPT_LIMIT: ClassVar[int] = int(CONTEXT_LENGTH * 0.20)
    LOCAL_MEMORY_LIMIT: ClassVar[int] = int(CONTEXT_LENGTH * 0.50)
    USER_MESSAGE_LIMIT: ClassVar[int] = int(CONTEXT_LENGTH * 0.1)
    CONVERSATION_PAGE_SIZE: ClassVar[int] = 10
    OBSERVATIONS_PAGE_SIZE: ClassVar[int] = 10
    AVERAGE_TOKEN_SIZE: ClassVar[int] = 4


class AgentState(BaseModel):
    """State for the chat agent workflow."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    epochs: int = Field(default=0)

    messages: list[AgentMessage]
    user_message: str
    agent_message: str = Field(default="")
    prompt: str = Field(default="")
    filepaths: list[str] = Field(default=[])

    # Memory Segments
    system_prompt: str = Field(default="")
    local_memory: str = Field(default="")
    recent_conversation_history: str = Field(default="")
    current_conversation_history_page: int = Field(default=1)

    # Multi-step reasoning fields
    phase: Phase = Field(default=Phase.NEED_FINAL)
    thought: AgentThought | None = Field(default=None)
    observations: list[ActionResult] = Field(default=[])

    # Quality assurance fields
    draft_response: str = Field(default="")

    # Error handling
    retry: int = Field(default=0)
    error_message: str | None = Field(default=None)

    stream_queue: asyncio.Queue = Field(default_factory=lambda: asyncio.Queue(maxsize=0))

    def build_conversation_history(self, curr_page: int = 1) -> str:
        """Build the conversation history from the state."""
        page_size = MemoryManagementConfig.CONVERSATION_PAGE_SIZE
        total_pages = len(self.messages) // page_size + 1
        message_start = (page_size * curr_page) - page_size
        message_end = message_start + page_size + 1

        curr_messages = self.messages[message_start:message_end]
        curr_messages.sort(key=lambda msg: msg.timestamp)

        summary = f"""
Page Size: {page_size}
Total Pages: {total_pages}
Current Page: {curr_page}
"""
        messages = "\n".join(msg.get_formatted_prompt() for msg in curr_messages)
        return f"""
## CONVERSATION HISTORY
{summary}

{messages}
"""

    def build_observation(self, curr_page: int = 1) -> str:
        """Build the observation from the state."""
        if not self.observations:
            return ""
        page_size = MemoryManagementConfig.OBSERVATIONS_PAGE_SIZE
        n = len(self.observations)
        total_pages = n // page_size + 1
        start = (page_size * curr_page) - page_size
        end = start + page_size + 1

        curr_obvs = self.observations[start:end]

        prompt = f"""\n## OBSERVATIONS
### Summary:
Total Pages: {total_pages}
Page Size: {page_size}
Current Page: {curr_page}

### Results
Below are the observations/result of your previous actions:\n
"""
        for idx, obs in enumerate(curr_obvs):
            prompt += f"### Result {(idx + 1)}.\n"
            prompt += f"{obs}\n\n"
        return prompt

    def list_available_temp_files(self) -> str:
        """List the available temporary files from the state."""
        if not self.filepaths:
            return ""
        paths = "\n-".join(self.filepaths)
        prompt = f"""
### TEMP FILES
Below are the temporary files you have access to in the current session:
{paths}
"""
        return prompt

    def get_error_message(self) -> Generator[str, None, None]:
        if not self.error_message:
            yield ""
        else:
            yield f"Got error: {self.error_message}"
            self.error_message = None

    def add_system_prompt(self, sys_prompt: str) -> None:
        """Add the system prompt to the state."""
        if len(sys_prompt) // MemoryManagementConfig.AVERAGE_TOKEN_SIZE > MemoryManagementConfig.SYSTEM_PROMPT_LIMIT:
            raise ValueError("System prompt is too long")

        self.system_prompt = sys_prompt

    def build_prompt(self) -> str:
        """Build the prompt from the state."""
        self.local_memory = f"""
# LOCAL MEMORY
{self.list_available_temp_files()}
{self.build_conversation_history()}
{self.build_observation()}
## CURRENT USER MESSAGE
{self.user_message}
"""
        local_memory_summary = f"""
## SUMMARY
Total Pages: {len(self.messages) // MemoryManagementConfig.CONVERSATION_PAGE_SIZE + 1}
Current Page: {self.current_conversation_history_page}
Local Memory Limit: {MemoryManagementConfig.LOCAL_MEMORY_LIMIT}
Current Local Memory Used: {len(self.local_memory) // MemoryManagementConfig.AVERAGE_TOKEN_SIZE}
"""

        prompt = f"""
{self.system_prompt}
{self.local_memory}
{local_memory_summary}
"""
        self.prompt = prompt
        self.epochs += 1

        shutil.rmtree("/tmp/prompts")
        os.makedirs("/tmp/prompts", exist_ok=True)
        with open(f"/tmp/prompts/p_{self.epochs}.md", "w") as f:
            f.write(prompt)
        return prompt


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
