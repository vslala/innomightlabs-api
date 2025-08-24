"""
Factory functions for creating ToolsManager instances.
"""

from typing import Optional

from app.chatbot.components.tools_manager import ToolsManager
from app.chatbot.components.tools_manager.yaml_tools_manager import YamlToolsManager
from app.chatbot.components.tools_manager.json_tools_manager import JsonToolsManager


def get_tools_manager(format_type: Optional[str] = None) -> ToolsManager:
    """
    Factory function to get the appropriate ToolsManager
    based on the format type or app configuration.

    Args:
        format_type: Optional format type ('yaml' or 'json').
                    If None, defaults to the app configuration.

    Returns:
        An instance of the appropriate ToolsManager implementation.
    """
    try:
        from app.common.config import AppConfig

        default_format = getattr(AppConfig, "TOOL_FORMAT", "yaml")
    except (ImportError, AttributeError):
        default_format = "yaml"

    format_type = (format_type or default_format or "yaml").lower()

    if format_type == "json":
        return JsonToolsManager()
    else:  # Default to YAML
        return YamlToolsManager()
