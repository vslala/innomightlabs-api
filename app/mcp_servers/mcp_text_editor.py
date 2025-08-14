#!/usr/bin/env python3
"""
MCP Text Editor Server
A minimal implementation of text editor tools using the MCP protocol.
"""

from typing import Dict, Optional
import os
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, Field
from loguru import logger

mcp_server = FastMCP("mcp_text_editor")


class Range(BaseModel):
    """Range in a text file, from start line to end line (inclusive)

    Examples:
        # Single line range (line 10)
        {
            "start_line": 10
        }

        # Multiple line range (lines 5-15)
        {
            "start_line": 5,
            "end_line": 15
        }
    """

    start_line: int = Field(..., description="Start line number (1-indexed)")
    end_line: Optional[int] = Field(None, description="End line number (1-indexed, inclusive), defaults to start_line if not provided")


@mcp_server.tool()
def create(path: str, content: str = "") -> Dict:
    """Create a new file with the given content

    Examples:
        # Create empty file
        create(path="/path/to/new_file.txt")

        # Create file with content
        create(
            path="/path/to/new_file.py",
            content="def hello():\n    print('Hello world!')\n"
        )

        # Create file in a nested directory
        create(
            path="/path/to/new/directory/file.json",
            content='{"key": "value"}'
        )
    """
    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        logger.debug(f"Ensuring directory exists for {path}")

        # Check if file already exists to avoid accidental overwrite
        if os.path.exists(path):
            logger.warning(f"File {path} already exists, refusing to overwrite")
            return {"success": False, "message": f"File {path} already exists. Use 'replace' to modify it."}

        with open(path, "w") as f:
            f.write(content)

        logger.info(f"Created file {path}")
        return {"success": True, "message": f"Created file {path}"}
    except Exception as e:
        logger.error(f"Failed to create file {path}: {str(e)}")
        return {"success": False, "message": f"Failed to create file: {str(e)}"}


@mcp_server.tool()
def view(path: str, range: Optional[Range] = None) -> Dict:
    """View content of a file, optionally within a specific line range

    Examples:
        # View entire file
        view(path="/path/to/file.txt")

        # View specific line (line 10)
        view(
            path="/path/to/file.txt",
            range={"start_line": 10}
        )

        # View range of lines (lines 5-15)
        view(
            path="/path/to/file.txt",
            range={"start_line": 5, "end_line": 15}
        )

        # View from specific line to end (from line 100)
        view(
            path="/path/to/file.txt",
            range={"start_line": 100, "end_line": None}
        )
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Attempted to view non-existent file: {path}")
            return {"success": False, "message": f"File {path} does not exist"}

        logger.debug(f"Opening file for reading: {path}")
        with open(path, "r") as f:
            lines = f.readlines()

        if range:
            start = max(0, range.start_line - 1)  # Convert to 0-indexed
            end = range.end_line or range.start_line
            selected_lines = lines[start:end]
            content = "".join(selected_lines)
            line_info = f"(lines {range.start_line}-{range.end_line or range.start_line})"
            logger.info(f"Viewing content of {path} {line_info}")
        else:
            content = "".join(lines)
            line_info = f"({len(lines)} lines total)"
            logger.info(f"Viewing full content of {path} {line_info}")

        return {"success": True, "message": f"Content of {path} {line_info}", "content": content}
    except Exception as e:
        logger.error(f"Failed to read file {path}: {str(e)}")
        return {"success": False, "message": f"Failed to read file: {str(e)}"}


@mcp_server.tool()
def delete(path: str) -> Dict:
    """Delete a file

    Examples:
        # Delete a specific file
        delete(path="/path/to/file.txt")

        # Delete a temporary file
        delete(path="/tmp/temporary_file.json")

        # Delete a log file
        delete(path="/var/log/app/debug.log")
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Attempted to delete non-existent file: {path}")
            return {"success": False, "message": f"File {path} does not exist"}

        logger.info(f"Deleting file: {path}")
        os.remove(path)
        logger.info(f"Successfully deleted file: {path}")
        return {"success": True, "message": f"Deleted file {path}"}
    except Exception as e:
        logger.error(f"Failed to delete file {path}: {str(e)}")
        return {"success": False, "message": f"Failed to delete file: {str(e)}"}


@mcp_server.tool()
def replace(path: str, old_str: str, new_str: str) -> Dict:
    """Replace occurrences of old_str with new_str in the file

    Examples:
        # Replace a single string
        replace(
            path="/path/to/file.txt",
            old_str="Hello",
            new_str="Hi"
        )

        # Replace code in a Python file
        replace(
            path="/path/to/script.py",
            old_str="def old_function_name()",
            new_str="def new_function_name()"
        )

        # Replace multiline content (using triple quotes)
        replace(
            path="/path/to/config.json",
            old_str='"debug": false',
            new_str='"debug": true'
        )

        # Replace all occurrences of a variable name
        replace(
            path="/path/to/code.js",
            old_str="var oldName",
            new_str="var newName"
        )
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Attempted to modify non-existent file: {path}")
            return {"success": False, "message": f"File {path} does not exist"}

        logger.debug(f"Reading file for replacement: {path}")
        with open(path, "r") as f:
            content = f.read()

        if old_str not in content:
            logger.warning(f"String '{old_str}' not found in {path}")
            return {"success": False, "message": f"String '{old_str}' not found in {path}"}

        # Replace and count occurrences
        new_content = content.replace(old_str, new_str)
        replacements = content.count(old_str)
        logger.debug(f"Found {replacements} occurrences to replace in {path}")

        logger.debug(f"Writing modified content to {path}")
        with open(path, "w") as f:
            f.write(new_content)

        logger.info(f"Replaced {replacements} occurrence(s) in {path}")
        return {"success": True, "message": f"Replaced {replacements} occurrence(s) of '{old_str}' with '{new_str}' in {path}"}
    except Exception as e:
        logger.error(f"Failed to replace content in {path}: {str(e)}")
        return {"success": False, "message": f"Failed to replace content: {str(e)}"}


if __name__ == "__main__":
    logger.info("Starting MCP Text Editor server")
    mcp_server.run("stdio")
