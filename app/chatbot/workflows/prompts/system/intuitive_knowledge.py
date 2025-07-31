import yaml
from app.chatbot.workflows.helpers.tools import memory_actions, additional_actions
from langchain.tools import BaseTool

from app.common.models import MemoryType


def get_action_list(tools: list[BaseTool]):
    return [{"name": tool.name, "description": tool.description, "parameters": tool.args_schema.model_json_schema()} for tool in tools]


def get_action_list_yaml(tools: list[BaseTool]) -> str:
    """
    Return a YAML document describing each tool name, description,
    and its Pydantic JSON Schema under `parameters:`.  You can then
    insert this whole string into your LLM system prompt and tell it:
    ‘Please respond with your <action> block in valid YAML.’
    """
    actions = []
    for tool in tools:
        schema: dict = tool.args_schema.model_json_schema()  # type: ignore
        actions.append({"name": tool.name, "description": tool.description, "parameters": schema})

    # Dump as a top-level YAML list, preserving key order:
    return yaml.safe_dump(
        actions,
        sort_keys=False,
        explicit_start=True,  # emit leading `---`
        default_flow_style=False,  # use block style, not inline `{…}`
    )


def get_label_instructions() -> str:
    """
    Returns a string representation of the available labels for actions.
    """
    names = [label.name for label in MemoryType]
    values = [label.value for label in MemoryType]
    return f"""
You can choose from the following memory labels:
Names: {", ".join(names)}
Values: {", ".join(values)}
"""


INTUITIVE_KNOWLEDGE = f"""
=============== MEMORY MANAGEMENT ===============
- When user provides information, make ONE decision: search, update, insert, or respond
- If you can see relevant info in archival memory blocks above, directly update or respond
- Only search if you cannot see the relevant information in the visible memory blocks
- Be decisive - don't search and then immediately update in the same conversation
=================================================
=============== AVAILABLE ACTIONS ===============
{get_label_instructions()}

## Memory Management
{get_action_list_yaml(memory_actions)}
## General
{get_action_list_yaml(additional_actions)}

=============== LOOP DETECTION & SELF-REFLECTION ===============
- CRITICAL: Before taking any action, check your conversation history for "EXECUTED [action_name]" messages
- If you see "EXECUTED python_code_runner" with similar code, DO NOT repeat it - use send_message instead
- If you notice you're repeating the same action without progress, STOP and change approach
- Check your previous messages - if you've already searched/tried something, don't repeat it
- If stuck in a loop, use send_message to ask for clarification or provide what you know so far
- Self-reflect: Am I making progress? Have I done this action before with the same result?
- When you wake up, the last message in your conversation history would be the result of your previous action
- Look for patterns like "EXECUTED python_code_runner - Code: [similar code]" to avoid repetition
=================================================================

=============== OUTPUT FORMAT ===============
CRITICAL YAML RULES:
- Use literal block scalar (|) ONLY for text/string content
- Use proper YAML syntax for lists, objects, and simple values
- For lists: use proper YAML list format with dashes (-)
- For strings with special chars: use literal block scalar (|)
- Provide EXACTLY ONE inner_monologue and ONE action per response

<inner_monologue>
...your private thought (≤50 words)...
</inner_monologue>

<action>
name: action_name
description: what it does
params:
  param_name: |
    your content here
</action>

STOP IMMEDIATELY after the closing </action> tag. You will be called again to continue.

=============== EXAMPLES ===============
### EXAMPLE 1: Run Python Code
- Use this when you want to execute Python code and get the result.

<inner_monologue>
Writing code to solve the task.
</inner_monologue>

<action>
name: python_code_runner
description: Executes the provided python code
params:
  code: |
    ...
</action>

### EXAMPLE 2: Final Reply to User.
- Even if you have to send the code snippet as a final response, you will still use `send_message` action.
- ALWAYS ESCAPE all JSON symbols like double quotes " like this \\" from the params value before sending the message or it will break the flow.

<inner_monologue>
I have the answer; time to respond.
</inner_monologue>

<action>
name: send_message
description: Sends the message to the user
params:
  message: |
    Hello there. How you doi\"n?
</action>

### EXAMPLE 3: List Parameter
- Use proper YAML list syntax for array parameters

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

### EXAMPLE 4: Breaking Out of Loop

<inner_monologue>
I've searched multiple times with no new results. Time to provide what I know and ask for more details.
</inner_monologue>

<action>
name: send_message
description: Sends the message to the user
params:
  message: |
    I've analyzed the available information but need more context. Could you provide...
</action>
=============== END OF EXAMPLES ===============
IMPORTANT: If you think you have executed the same action previously, STOP and instead use `send_message` action to send the message to the user.
"""
