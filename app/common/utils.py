from loguru import logger
import re
from typing import Callable, Any, Optional
from pydantic import BaseModel
from app.chatbot.chatbot_models import ActionResult, AgentState


def write_to_file(filepath: str, content: str) -> None:
    """
    Write content to a file, creating directories if they don't exist.
    """
    import os

    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, "w") as f:
        f.write(content)
    logger.info(f"Content written to {filepath}")


def extract_tag_content(text: str, tag: str) -> list[str]:
    """
    Extracts all text contents inside provided tag.
    """
    esc = re.escape(tag)
    pattern = rf"<{esc}>(.*?)</{esc}>"
    return re.findall(pattern, text, flags=re.DOTALL)


class SimpleTool:
    """Simple tool wrapper to replace LangChain dependency"""

    def __init__(self, name: str, description: str, func: Callable, args_schema: Optional[type[BaseModel]] = None, return_direct: bool = False):
        self.name = name
        self.description = description
        self.func = func
        self.args_schema = args_schema or type("EmptySchema", (BaseModel,), {})
        self.return_direct = return_direct
        self.coroutine = func  # For compatibility with existing code

    async def invoke(self, state: AgentState, input_data: Any) -> ActionResult:
        """Invoke the tool function"""
        return await self.func(state, input_data)


def tool(name: str, description: str = "", args_schema: Optional[type[BaseModel]] = None, return_direct: bool = False):
    """Decorator to create a simple tool"""

    def decorator(func: Callable) -> SimpleTool:
        tool_description = description or func.__doc__ or "No description available"
        return SimpleTool(name, tool_description, func, args_schema, return_direct)

    return decorator
