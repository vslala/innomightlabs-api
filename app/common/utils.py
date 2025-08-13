from loguru import logger
import re


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
