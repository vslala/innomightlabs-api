#!/usr/bin/env python3
"""
MCP Text Editor Server
A minimal implementation of text editor tools using the MCP protocol.
"""

from typing import Dict, Optional
import os
import glob
import fnmatch
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


@mcp_server.tool()
def list_files(pattern: str) -> Dict:
    """List files matching a pattern

    Examples:
        # List all Python files in a directory
        list_files(pattern="app/chatbot/*.py")

        # List all files recursively
        list_files(pattern="app/**/*.py")

        # List specific file types
        list_files(pattern="*.json")
    """
    try:
        matches = glob.glob(pattern, recursive=True)
        matches = [os.path.abspath(match) for match in matches if os.path.isfile(match)]
        matches.sort()

        logger.info(f"Found {len(matches)} files matching pattern '{pattern}'")
        return {"success": True, "message": f"Found {len(matches)} files matching pattern '{pattern}'", "files": matches}
    except Exception as e:
        logger.error(f"Failed to list files with pattern {pattern}: {str(e)}")
        return {"success": False, "message": f"Failed to list files: {str(e)}"}


@mcp_server.tool()
def append(path: str, content: str) -> Dict:
    """Append content to the end of a file

    Examples:
        # Append a line to a file
        append(
            path="/path/to/file.txt",
            content="This line will be added at the end\n"
        )

        # Append a log entry
        append(
            path="/path/to/log.txt",
            content="[2025-08-24] New log entry\n"
        )

        # Append code to a Python file
        append(
            path="/path/to/script.py",
            content="\n\ndef new_function():\n    print('This is a new function')\n"
        )
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Attempted to append to non-existent file: {path}")
            return {"success": False, "message": f"File {path} does not exist"}

        logger.debug(f"Opening file for appending: {path}")
        with open(path, "a") as f:
            f.write(content)

        logger.info(f"Successfully appended content to {path}")
        return {"success": True, "message": f"Appended content to {path}"}
    except Exception as e:
        logger.error(f"Failed to append to file {path}: {str(e)}")
        return {"success": False, "message": f"Failed to append to file: {str(e)}"}


@mcp_server.tool()
def tree(path: str, max_depth: int = 3) -> Dict:
    """Visualize directory structure in a tree format

    Examples:
        # View project structure
        tree(path="/path/to/project")

        # View with limited depth
        tree(
            path="/path/to/project",
            max_depth=2
        )
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Directory {path} does not exist")
            return {"success": False, "message": f"Directory {path} does not exist"}

        if not os.path.isdir(path):
            logger.warning(f"{path} is not a directory")
            return {"success": False, "message": f"{path} is not a directory"}

        result = []

        def generate_tree(dir_path, prefix="", depth=0):
            if depth > max_depth:
                return

            entries = sorted(os.listdir(dir_path))
            dirs = [e for e in entries if os.path.isdir(os.path.join(dir_path, e))]
            files = [e for e in entries if os.path.isfile(os.path.join(dir_path, e))]

            # Process directories
            for i, dirname in enumerate(dirs):
                is_last_dir = i == len(dirs) - 1 and len(files) == 0
                current_prefix = "└── " if is_last_dir else "├── "
                result.append(f"{prefix}{current_prefix}{dirname}/")

                # Prepare prefix for subdirectories
                new_prefix = prefix + ("    " if is_last_dir else "│   ")
                generate_tree(os.path.join(dir_path, dirname), new_prefix, depth + 1)

            # Process files
            for i, filename in enumerate(files):
                is_last = i == len(files) - 1
                result.append(f"{prefix}{'└── ' if is_last else '├── '}{filename}")

        # Start with the root directory name
        root_name = os.path.basename(os.path.abspath(path))
        result.append(f"{root_name}/")
        generate_tree(path, "", 0)

        tree_output = "\n".join(result)
        logger.info(f"Generated directory tree for {path} with max depth {max_depth}")
        return {"success": True, "message": f"Directory structure for {path} (max depth: {max_depth})", "tree": tree_output}
    except Exception as e:
        logger.error(f"Failed to generate tree for {path}: {str(e)}")
        return {"success": False, "message": f"Failed to generate tree: {str(e)}"}


@mcp_server.tool()
def search_in_files(path: str, pattern: str, file_glob: str = "*.*") -> Dict:
    """Search for text pattern in files matching glob pattern

    Examples:
        # Search for a function in Python files
        search_in_files(
            path="/path/to/project",
            pattern="def process_data",
            file_glob="*.py"
        )

        # Search for configuration in JSON files
        search_in_files(
            path="/path/to/configs",
            pattern="debug_mode",
            file_glob="*.json"
        )
    """
    try:
        if not os.path.exists(path):
            logger.warning(f"Path {path} does not exist")
            return {"success": False, "message": f"Path {path} does not exist"}

        results = []
        file_count = 0
        match_count = 0

        # Handle both directory and single file cases
        if os.path.isdir(path):
            search_path = os.path.join(path, "**", file_glob)
            files = glob.glob(search_path, recursive=True)
        else:
            # If path is a file and matches the glob pattern
            if fnmatch.fnmatch(os.path.basename(path), file_glob):
                files = [path]
            else:
                files = []

        for file_path in files:
            if not os.path.isfile(file_path):
                continue

            file_count += 1
            try:
                with open(file_path, "r", errors="replace") as f:
                    lines = f.readlines()

                file_matches = []
                for i, line in enumerate(lines):
                    if pattern in line:
                        match_count += 1
                        file_matches.append(
                            {
                                "line_number": i + 1,  # 1-indexed line numbers
                                "line": line.rstrip(),
                            }
                        )

                if file_matches:
                    rel_path = os.path.relpath(file_path, path) if os.path.isdir(path) else os.path.basename(file_path)
                    results.append({"file": rel_path, "matches": file_matches})
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {str(e)}")

        logger.info(f"Found {match_count} matches in {len(results)} files (searched {file_count} files)")
        return {"success": True, "message": f"Found {match_count} matches in {len(results)} files (searched {file_count} files)", "results": results}
    except Exception as e:
        logger.error(f"Failed to search in files: {str(e)}")
        return {"success": False, "message": f"Failed to search in files: {str(e)}"}


if __name__ == "__main__":
    logger.info("Starting MCP Text Editor server")
    mcp_server.run("stdio")
