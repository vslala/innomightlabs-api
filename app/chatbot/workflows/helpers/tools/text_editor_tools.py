from enum import Enum
import json
from typing import Optional, Union
from pydantic import BaseModel
from strands_tools import editor as strands_text_editor

from app.chatbot.chatbot_models import ActionResult, AgentState
from langchain.tools import tool

import os


os.environ["BYPASS_TOOL_CONSENT"] = "true"
DIR_PREFIX = "/tmp/innomightlabs/"
if not os.path.exists(DIR_PREFIX):
    os.makedirs(DIR_PREFIX, exist_ok=True)


class TextEditorCommand(Enum):
    VIEW = "view"
    CREATE = "create"
    STR_REPLACE = "str_replace"
    PATTERN_REPLACE = "pattern_replace"
    INSERT = "insert"
    FIND_LINE = "find_line"
    UNDO_EDIT = "undo_edit"


class TextEditorInputParams(BaseModel):
    command: TextEditorCommand
    path: str
    file_text: Optional[str] = None
    insert_line: Optional[Union[str, int]] = None
    new_str: Optional[str] = None
    old_str: Optional[str] = None
    pattern: Optional[str] = None
    search_text: Optional[str] = None
    fuzzy: bool = False
    view_range: Optional[list[int]] = None


@tool(
    "text_editor",
    description="""
    Editor tool designed to do changes iteratively on multiple files.

    This tool provides a comprehensive interface for file operations, including viewing,
    creating, modifying, and searching files with rich output formatting. It features
    syntax highlighting, smart line finding, and automatic backups for safety.

    IMPORTANT ERROR PREVENTION:
    1. Required Parameters:
       • file_text: REQUIRED for 'create' command - content of file to create
       • search_text: REQUIRED for 'find_line' command - text to search
       • insert command: BOTH new_str AND insert_line REQUIRED

    2. Command-Specific Requirements:
       • create: Must provide file_text, file_text is required for create command
       • str_replace: Both old_str and new_str are required for str_replace command
       • pattern_replace: Both pattern and new_str required
       • insert: Both new_str and insert_line required
       • find_line: search_text required

    3. Path Handling:
       • Use absolute paths (e.g., /Users/name/file.txt)
       • Or user-relative paths (~/folder/file.txt)
       • Ensure parent directories exist for create command

    Command Details:
    --------------
    1. view:
       • Displays file content with syntax highlighting
       • Shows directory structure for directory paths
       • Supports viewing specific line ranges with view_range

    2. create:
       • Creates new files with specified content
       • Creates parent directories if they don't exist
       • Caches content for subsequent operations

    3. str_replace:
       • Replaces exact string matches in a file
       • Creates automatic backup before modification
       • Returns details about number of replacements

    4. pattern_replace:
       • Uses regex patterns for advanced text replacement
       • Validates patterns before execution
       • Creates automatic backup before modification

    5. insert:
       • Inserts text after a specified line
       • Supports finding insertion points by line number or search text
       • Shows context around insertion point

    6. find_line:
       • Finds line numbers matching search text
       • Supports fuzzy matching for flexible searches
       • Shows context around found line

    7. undo_edit:
       • Reverts to the most recent backup
       • Removes the backup file after restoration
       • Updates content cache with restored version

    Smart Features:
    ------------
    • Content caching improves performance by reducing file reads
    • Fuzzy search allows finding lines with approximate matches
    • Automatic backups before modifications ensure safety
    • Rich output formatting enhances readability of results

    Args:
        command: The commands to run: `view`, `create`, `str_replace`, `pattern_replace`,
                `insert`, `find_line`, `undo_edit`.
        path: Absolute path to file or directory, e.g. `/repo/file.py` or `/repo`.
                User paths with tilde (~) are automatically expanded.
        file_text: Required parameter of `create` command, with the content of the file to be created.
        insert_line: Required parameter of `insert` command. The `new_str` will be inserted AFTER
                the line `insert_line` of `path`. Can be a line number or search text.
        new_str: Required parameter containing the new string for `str_replace`,
                `pattern_replace` or `insert` commands.
        old_str: Required parameter of `str_replace` command containing the exact string to replace.
        pattern: Required parameter of `pattern_replace` command containing the regex pattern to match.
        search_text: Text to search for in `find_line` command. Supports fuzzy matching.
        fuzzy: Enable fuzzy matching for `find_line` command.
        view_range: Optional parameter of `view` command. Line range to show [start, end].
                Supports negative indices.

    Returns:
        Dict containing status and response content in the format:
        {
            "status": "success|error",
            "content": [{"text": "Response message"}]
        }

        Success case: Returns details about the operation performed
        Error case: Returns information about what went wrong

    Examples:
        1. View a file:
           editor(command="view", path="/path/to/file.py")

        2. Create a new file:
           editor(command="create", path="/path/to/file.txt", file_text="Hello World")

        3. Replace text:
           editor(command="str_replace", path="/path/to/file.py", old_str="old", new_str="new")

        4. Insert after line 10:
           editor(command="insert", path="/path/to/file.py", insert_line=10, new_str="# New line")

        5. Insert after a specific text:
           editor(command="insert", path="/path/to/file.py", insert_line="def main", new_str="    # Comment")

        6. Find a line containing text:
           editor(command="find_line", path="/path/to/file.py", search_text="import os")

        7. Undo recent change:
           editor(command="undo_edit", path="/path/to/file.py")
    """,
    args_schema=TextEditorInputParams,
    infer_schema=False,
    return_direct=True,
)
async def text_editor(state: AgentState, input: TextEditorInputParams) -> ActionResult:
    input.path = f"{DIR_PREFIX}{input.path}"

    output = strands_text_editor.editor(
        command=input.command.value,
        path=input.path,
        file_text=input.file_text,
        insert_line=input.insert_line,
        new_str=input.new_str,
        old_str=input.old_str,
        pattern=input.pattern,
        search_text=input.search_text,
        fuzzy=input.fuzzy,
        view_range=input.view_range,
    )

    return ActionResult(
        thought=f"Command `text_editor` executed with params: `{input.model_dump_json()}`",
        action=f"text_editor > {input.command.value}",
        result=json.dumps(output),
    )
