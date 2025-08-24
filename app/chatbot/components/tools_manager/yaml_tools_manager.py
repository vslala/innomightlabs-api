"""
YAML implementation of ToolsManager.
"""

import yaml
from typing import Dict, List, Optional, Any

from loguru import logger
from app.common.utils import extract_tag_content
from app.chatbot.chatbot_models import Action, ActionResult, AgentState, AgentThought

# Import from parent package using absolute import to avoid circular imports
from app.chatbot.components.tools_manager import ToolsManager
# Access tools_by_name from self instead of importing Tools to avoid circular imports


class YamlToolsManager(ToolsManager):
    """Implementation of ToolsManager that uses YAML format"""

    async def parse_tool_calls(self, response_text: str) -> List[Optional[Action]]:
        """Parse YAML tool calls from response text"""
        actions = []
        try:
            # Log the complete response for debugging
            logger.debug(f"Parsing response text for actions:\n{response_text}")

            action_blocks = extract_tag_content(response_text, "action") or []
            logger.info(f"Found {len(action_blocks)} action blocks")

            for idx, action_yaml in enumerate(action_blocks):
                action_yaml = action_yaml.strip()
                logger.debug(f"Processing action block {idx + 1}:\n{action_yaml}")

                try:
                    action_data = yaml.safe_load(action_yaml)
                    logger.debug(f"Parsed YAML data: {action_data}")

                    # Check if action has required fields
                    if not isinstance(action_data, dict) or "name" not in action_data:
                        logger.error(f"Invalid action format - missing 'name' field: {action_data}")
                        continue

                    # Explicitly log the tool name being called
                    logger.info(f"Tool call detected: {action_data.get('name')}")

                    action = Action.model_validate(action_data)
                    logger.info(f"Validated action: {action.name}")
                    actions.append(action)
                except yaml.YAMLError as e:
                    logger.error(f"YAML parsing error: {str(e)}")
                    logger.debug(f"Invalid YAML format: {action_yaml}")
                except Exception as e:
                    logger.error(f"Failed to parse YAML action: {str(e)}")
                    logger.debug(f"Invalid YAML content: {action_yaml}")
        except Exception as e:
            logger.error(f"Error extracting actions: {str(e)}")

        logger.info(f"Parsed {len(actions)} valid actions")
        return actions

    async def execute_tool(self, state: AgentState, thought: AgentThought) -> ActionResult:
        """Execute the specified tool"""
        action = thought.action
        tool_name = action.name

        logger.info(f"YamlToolsManager executing tool: {tool_name}")
        logger.debug(f"Tool params: {action.params}")

        # Check if the tool exists
        if tool_name not in self.tools_by_name:
            available_tools = list(self.tools_by_name.keys())
            error_msg = f"Unknown tool: {tool_name}. Available tools: {available_tools}"
            logger.error(error_msg)
            raise ValueError(error_msg)

        selected_tool = self.tools_by_name[tool_name]
        logger.info(f"Found tool: {tool_name}, description: {selected_tool.description[:50]}...")
        input_params = action.params

        try:
            # Special logging for send_message tool
            if tool_name == "send_message":
                logger.info(f"Executing send_message with message: {input_params.get('message', '')[:100]}...")

            # Handle tool execution (similar to existing execute_actions)
            if hasattr(selected_tool, "args_schema") and hasattr(selected_tool, "invoke"):
                # LangChain tool
                logger.debug("Executing as LangChain-compatible tool")
                tool_params = {"thought": thought, **input_params}
                logger.debug(f"Creating tool input with params: {tool_params}")

                try:
                    tool_input = selected_tool.args_schema(**tool_params)
                    logger.debug(f"Tool input created: {tool_input}")
                except Exception as e:
                    logger.error(f"Error creating tool input: {str(e)}")
                    # Try to create a more detailed error message
                    schema_fields = getattr(selected_tool.args_schema, "__annotations__", {})
                    logger.error(f"Tool schema fields: {schema_fields}")
                    logger.error(f"Provided params: {tool_params}")
                    raise

                result = await selected_tool.coroutine(state, tool_input)
                logger.info(f"Tool {tool_name} executed successfully")
                return ActionResult.model_validate(result)
            else:
                # Custom async function
                logger.debug("Executing as custom async function")
                result = await selected_tool.func(state)
                logger.info(f"Custom function {tool_name} executed successfully")
                return result
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            logger.exception("Detailed exception info:")
            raise

    @property
    def format_name(self) -> str:
        return "yaml"

    @property
    def output_format_instructions(self) -> str:
        return """
      <inner_monologue>
      ...your private thought (≤50 words)...
      </inner_monologue>

      <action>
      name: action_name
      description: what it does
      request_heartbeat: true|false
      reason_for_heartbeat: ...reason for heartbeat...
      params:
        param_name: |
          your content here
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
          name: python_code_runner
          description: Executes the provided python code
          request_heartbeat: true
          reason_for_heartbeat: Need to run the python code to get the result
          params:
            code: |
              import math
              result = math.sqrt(16)
              print(f'The square root is {result}')
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
                "content": """
          <action>
          name: send_message
          description: Sends the message to the user
          params:
            message: |
              Hello there. How you doing?
          </action>
        """,
            },
            {
                "title": "List Parameter",
                "content": """
          <inner_monologue>
          Removing redundant memory entries.
          </inner_monologue>

          <action>
          name: archival_memory_evict
          description: Remove memory blocks
          params:
            reference: |
              Cleaning up memory
            memory_ids:
              - "cd5ca3cd-28b7-4e32-bb3a-633dea225055"
              - "7c23c408-ab06-4b8b-b328-5047551e0a25"
          </action>
        """,
                "notes": "Use proper YAML list syntax for array parameters",
            },
        ]

    @property
    def format_rules(self) -> List[str]:
        return [
            'ALWAYS wrap string values in double quotes (") when they contain special characters, colons, or multiline content',
            "Use literal block scalar (|) for long multiline text content",
            'For simple strings with colons (like "Name: John"), ALWAYS use quotes: old_text: "Name: John"',
            "Use proper YAML syntax for lists, objects, and simple values",
            "For lists: use proper YAML list format with dashes (-)",
            'ALWAYS quote date values like "2025-08-01" to prevent YAML auto-parsing',
            "Provide EXACTLY ONE inner_monologue and ONE action per response",
        ]
