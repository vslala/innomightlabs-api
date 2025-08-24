"""
ToolsManager module for managing tool interactions between LLM and the system.

This module provides classes for converting tool definitions to different formats (YAML/JSON),
parsing LLM responses to extract tool calls, and executing those tools.
"""

from abc import ABC, abstractmethod
from collections import defaultdict
from enum import Enum
from typing import Dict, List, Optional, Any


from app.common.utils import SimpleTool as BaseTool
from app.chatbot.chatbot_models import Action, ActionResult, AgentState, AgentThought


class ToolCategory(Enum):
    CORE = ("core",)
    MEMORY = ("memory",)
    MCP = ("mcp",)
    CODE = ("code",)
    MISC = "misc"


class ToolsManager(ABC):
    """
    Abstract base class for managing tool interactions between LLM and system.
    This class is responsible for providing tool schemas to the LLM,
    parsing LLM responses to extract tool calls, and executing those tools.
    """

    tools_by_name = {}
    tools_by_category = defaultdict(list[BaseTool])

    def register_tool(self, tool_category: ToolCategory, tool: BaseTool):
        """
        Register a tool with the manager.
        """
        self.tools_by_category[tool_category.name].append(tool)
        self.tools_by_name[tool.name] = tool

    def remove_tool(self, tool_category: ToolCategory, tool: BaseTool):
        """
        Remove a tool from the manager.
        """
        given_category = self.tools_by_category[tool_category.name]

        for idx, t in enumerate(given_category):
            if t.name == tool.name:
                del given_category[idx]
                del self.tools_by_name[tool.name]
                break

    def get_tools_schema(self) -> dict[str, list[Action]]:
        """
        Convert tools to the appropriate schema format (YAML or JSON)
        for inclusion in the LLM prompt.
        """
        action_by_category = defaultdict(list[Action])
        for _, tool in self.tools_by_name.items():
            # Get category from tool or use 'misc' as default
            category = getattr(tool, "category", ToolCategory.MISC.name)

            action_by_category[category].append(
                Action(
                    name=tool.name,
                    description=tool.description,
                    params=tool.args_schema.model_json_schema(),
                )
            )

        return action_by_category

    @abstractmethod
    async def parse_tool_calls(self, response_text: str) -> List[Optional[Action]]:
        """
        Parse the LLM response text to extract tool calls in the
        appropriate format (YAML or JSON).

        Returns a list of Actions extracted from the response, or an empty list
        if no valid tool calls were found.
        """
        pass

    @abstractmethod
    async def execute_tool(self, state: AgentState, thought: AgentThought) -> ActionResult:
        """
        Execute the specified tool with the given parameters
        and return the result.
        """
        pass

    @property
    @abstractmethod
    def format_name(self) -> str:
        """Return the format name ('yaml' or 'json')"""
        pass

    @property
    @abstractmethod
    def output_format_instructions(self) -> str:
        """Return the instructions for how the LLM should format its response"""
        pass

    @property
    @abstractmethod
    def output_examples(self) -> List[Dict[str, Any]]:
        """Return examples of properly formatted tool calls"""
        pass

    @property
    @abstractmethod
    def format_rules(self) -> List[str]:
        """Return rules for proper formatting in this format"""
        pass
