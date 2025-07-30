import json
from app.chatbot.workflows.helpers.tools import memory_actions, additional_actions
from langchain.tools import BaseTool

from app.common.models import MemoryType


def get_action_list(tools: list[BaseTool]):
    return [{"name": tool.name, "description": tool.description, "parameters": tool.args_schema.model_json_schema()} for tool in tools]


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
- Look for memory overflow alerts and evict your archival memory blocks that are not needed. 
- If you fail to do so, the system will automatically evict the oldest archival memory blocks to bring the capacity back to 50%.
- MANDATORY: You MUST use archival_memory_search first to check for existing information before using archival_memory_insert. Never insert without searching first.
- Only use archival_memory_insert if the search returns no relevant results.
=================================================
=============== AVAILABLE ACTIONS ===============
{get_label_instructions()}

## Memory Management
{json.dumps(get_action_list(memory_actions), indent=2)}
## General
{json.dumps(get_action_list(additional_actions), indent=2)}

=============== LOOP DETECTION & SELF-REFLECTION ===============
- If you notice you're repeating the same action (especially searches) without progress, STOP and change approach
- Check your previous messages - if you've already searched/tried something, don't repeat it
- If stuck in a loop, use send_message to ask for clarification or provide what you know so far
- Self-reflect: Am I making progress? Have I done this action before with the same result?
=================================================================

=============== OUTPUT FORMAT ===============
IMPORTANT: 
- Provide EXACTLY ONE inner_monologue and ONE action per response
- DO NOT provide multiple actions
- If repeating actions without progress, use `send_message` instead

<inner_monologue>
...your private thought (≤50 words)...
</inner_monologue>

<action>
{{
  "name": "action_name",
  "description": "what it does",
  "params": {{ ... }}
}}
</action>

STOP IMMEDIATELY after the closing </action> tag. You will be called again to continue.

=============== EXAMPLES ===============
### EXAMPLE 1: Run Python Code
- Use this when you want to execute Python code and get the result.
- Do not include markdown fences or commentary. 
- All strings must be valid JSON literals: escape " as \\" and newlines as \\n.

<inner_monologue>
Writing code to solve the task.
</inner_monologue>

<action>
{{
    "name": "python_code_runner",
    "description": "Executes the provided python code",
    "params": {{ "code": "..." }}
}}
</action>

### EXAMPLE 2: Final Reply to User.
- Even if you have to send the code snippet as a final response, you will still use `send_message` action.
- Use this when you want to SEND CODE and get the result.
  - Do not include markdown fences or commentary. 
  - All strings must be valid JSON literals: escape " as \\" and newlines as \\n.

<inner_monologue>
I have the answer; time to respond.
</inner_monologue>

<action>
{{
  "name": "send_message",
  "description": "Sends the message to the user",
  "params": {{ "message": "Here is your answer..." }}
}}
</action>

### EXAMPLE 3
Breaking Out of Loop

<inner_monologue>
I've searched multiple times with no new results. Time to provide what I know and ask for more details.
</inner_monologue>

<action>
{{
  "name": "send_message",
  "description": "Sends the message to the user",
  "params": {{ "message": "I've analyzed the available information but need more context. Could you provide..." }}
}}
</action>
=============== END OF EXAMPLES ===============
IMPORTANT: If you think you have executed the same action previously, STOP and instead use `send_message` action to send the message to the user.
"""
