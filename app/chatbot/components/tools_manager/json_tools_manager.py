"""
JSON implementation of ToolsManager.
"""

import json
from typing import Dict, List, Optional, Any

from loguru import logger
from app.common.utils import extract_tag_content
from app.chatbot.chatbot_models import Action, ActionResult, AgentState, AgentThought
from app.chatbot.components.tools_manager import ToolsManager
# Access tools_by_name from self instead of importing Tools to avoid circular imports


class JsonToolsManager(ToolsManager):
    """Implementation of ToolsManager that uses JSON format"""

    async def parse_tool_calls(self, response_text: str) -> List[Optional[Action]]:
        """Parse JSON tool calls from response text"""
        actions = []
        try:
            for action_json in extract_tag_content(response_text, "action") or []:
                action_json = action_json.strip()
                try:
                    action_data = json.loads(action_json)
                    action = Action.model_validate(action_data)
                    actions.append(action)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON action: {str(e)}")
                    logger.error("Expected JSON format but received invalid JSON. Make sure the LLM is configured to output JSON.")
                    logger.debug(f"Invalid JSON: {action_json}")
                except Exception as e:
                    logger.error(f"Failed to parse JSON action: {str(e)}")
                    logger.debug(f"Invalid JSON: {action_json}")
        except Exception as e:
            logger.error(f"Error extracting actions: {str(e)}")

        return actions

    async def execute_tool(self, state: AgentState, thought: AgentThought) -> ActionResult:
        """Execute the specified tool"""
        action = thought.action
        tool_name = action.name

        if tool_name not in self.tools_by_name:
            error_msg = f"Unknown tool: {tool_name}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        selected_tool = self.tools_by_name[tool_name]
        input_params = action.params

        try:
            # Handle tool execution (similar to existing execute_actions)
            if hasattr(selected_tool, "args_schema") and hasattr(selected_tool, "invoke"):
                # LangChain tool
                tool_params = {"thought": thought, **input_params}
                tool_input = selected_tool.args_schema(**tool_params)
                result = await selected_tool.coroutine(state, tool_input)
                return ActionResult.model_validate(result)
            else:
                # Custom async function
                result = await selected_tool.func(state)
                return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            raise

    @property
    def format_name(self) -> str:
        return "json"

    @property
    def output_format_instructions(self) -> str:
        return """
      <inner_monologue>
      ...your private thought (≤50 words)...
      </inner_monologue>

      <action>
      {
        "name": "action_name",
        "description": "what it does",
        "request_heartbeat": true|false,
        "reason_for_heartbeat": "...reason for heartbeat...",
        "params": {
          "param_name": "your content here"
        }
      }
      </action>
      
      STOP IMMEDIATELY after the closing </action> tag. You will be called again to continue.
    """

    @property
    def output_examples(self) -> List[Dict[str, Any]]:
        return [
            {
                "title": "Run Python Code",
                "content": """
          <inner_monologue>
          Writing code to solve the task.
          </inner_monologue>

          <action>
          {
            "name": "python_code_runner",
            "description": "Executes the provided python code",
            "request_heartbeat": true,
            "reason_for_heartbeat": "Need to run the python code to get the result",
            "params": {
              "code": "import math\\nresult = math.sqrt(16)\\nprint(f'The square root is {result}')"
            }
          }
          </action>
        """,
                "notes": """
          The system will perform following actions after receiving the heartbeat request:
            1. Perform the current action e.g. executing python code
            2. Add the result of the action to your current context
            3. Invoke you again iff you have provided the heartbeat or else the flow breaks. Use this to perform multi-step actions

            Now you will check observations to find the result and use it to answer the user or perform another action. \
            That's how you can chain your actions.
        """,
            },
            {
                "title": "Final Reply to User",
                "content": f"""
          <action>
          {Action(name="send_message", description="Sends the message to the user", params={"message": "Hello there. How you do'in?"}).model_dump_json()}
          </action>
        """,
            },
            {
                "title": "List Parameter",
                "content": f"""
          <inner_monologue>
          Removing redundant memory entries.
          </inner_monologue>

          <action>
          {
                    Action(
                        name="memory_evict",
                        description="Remove memory blocks",
                        request_heartbeat=True,
                        reason_for_heartbeat="I want to send the message to user after evicting the memory",
                        params={"text": "User lives in London"},
                    ).model_dump_json()
                }
          </action>
        """,
                "notes": "Use proper JSON array syntax for array parameters",
            },
        ]

    @property
    def format_rules(self) -> List[str]:
        return [
            "Always use valid JSON syntax for your action blocks",
            'For string values, use double quotes with proper escaping: "Hello \\"world\\""',
            "Ensure all property names are in double quotes",
            "Use proper JSON notation for arrays and objects",
            'Arrays should use square brackets: ["item1", "item2"]',
            "Nested objects should use proper nesting with braces",
            "Do not include trailing commas after the last property",
            'For multiline text, include newline characters in the string: "line1\\nline2"',
            "Provide EXACTLY ONE inner_monologue and ONE action per response",
        ]
