from pydantic import BaseModel
from app.chatbot.chatbot_models import ActionResult, AgentState
from app.common.utils import tool


class SubAgentToolParams(BaseModel):
    prompt: str


@tool(
    name="sub-agent",
    description="""
    This is a sub-agent.
    """,
    args_schema=SubAgentToolParams,
)
def sub_agent_tool(state: AgentState, input: SubAgentToolParams) -> ActionResult:
    return ActionResult(
        thought="I am a sub-agent",
        action="sub-agent",
        result=input.prompt,
    )
