"""
Multilingual Prompt Loader
多语言提示词加载器
===========================

=== 本地特色：全面中文汉化 ===

本模块是 Auto-Claude-Chinese 的核心特色之一。
默认使用中文提示词（PROMPT_LANGUAGE=zh-CN），缺失时自动回退英文。

Centralized utility for loading prompt files with language support.
Supports fallback from localized prompts to English defaults.

中文提示词覆盖：
- 核心流程提示词：24 个（planner, coder, qa_reviewer 等）
- GitHub PR 审查提示词：20 个（pr_reviewer, security_agent 等）

切换语言：设置环境变量 PROMPT_LANGUAGE=en 可切换回英文。
"""

import os
from pathlib import Path
from typing import Optional


def get_prompt_path(prompt_name: str, base_dir: Optional[Path] = None) -> Path:
    """
    Get the path to a prompt file, supporting multiple languages.

    Language selection priority:
    1. Use PROMPT_LANGUAGE (defaults to zh-CN in this fork) and try prompts/{LANG}/{prompt_name}.md
    2. Fall back to prompts/{prompt_name}.md (English fallback)

    Args:
        prompt_name: Name of the prompt file without extension (e.g., "planner", "coder")
                    Can include subdirectories (e.g., "mcp_tools/electron_validation")
        base_dir: Base directory containing the prompts/ folder.
                 If None, uses the parent directory of prompts_pkg/

    Returns:
        Path to the prompt file (guaranteed to exist or raises FileNotFoundError)

    Raises:
        FileNotFoundError: If neither localized nor default prompt exists

    Examples:
        >>> get_prompt_path("planner")
        Path("/path/to/prompts/planner.md")  # or prompts/zh-CN/planner.md

        >>> get_prompt_path("mcp_tools/electron_validation")
        Path("/path/to/prompts/mcp_tools/electron_validation.md")
    """
    # Determine base directory
    if base_dir is None:
        # Default: prompts/ is sibling to prompts_pkg/
        base_dir = Path(__file__).parent.parent / "prompts"
    else:
        base_dir = Path(base_dir) / "prompts"

    # Auto-Claude-Chinese defaults to zh-CN; keep prompts/zh-CN synced with upstream English.
    # See scripts/i18n/README.md for the maintenance workflow.
    language = os.environ.get("PROMPT_LANGUAGE", "zh-CN")

    # Ensure .md extension
    if not prompt_name.endswith(".md"):
        prompt_name = f"{prompt_name}.md"

    # Try localized version first (if not English)
    if language != "en":
        localized_path = base_dir / language / prompt_name
        if localized_path.exists():
            return localized_path

    # Fall back to English default
    default_path = base_dir / prompt_name
    if default_path.exists():
        return default_path

    # Neither exists - raise error with helpful message
    tried_paths = []
    if language != "en":
        tried_paths.append(str(base_dir / language / prompt_name))
    tried_paths.append(str(default_path))

    raise FileNotFoundError(
        f"Prompt file '{prompt_name}' not found.\n"
        f"Tried paths:\n" + "\n".join(f"  - {p}" for p in tried_paths)
    )


def load_prompt(prompt_name: str, base_dir: Optional[Path] = None) -> str:
    """
    Load a prompt file with language support.

    This is a convenience wrapper around get_prompt_path() that also reads the file.

    Args:
        prompt_name: Name of the prompt file without extension
        base_dir: Base directory containing the prompts/ folder

    Returns:
        Content of the prompt file

    Raises:
        FileNotFoundError: If prompt file doesn't exist

    Examples:
        >>> content = load_prompt("planner")
        >>> content = load_prompt("mcp_tools/electron_validation")
    """
    prompt_path = get_prompt_path(prompt_name, base_dir)
    return prompt_path.read_text(encoding="utf-8")


def get_prompts_dir(base_dir: Optional[Path] = None) -> Path:
    """
    Get the prompts directory for the current language.

    Returns the localized directory if PROMPT_LANGUAGE is set (or defaults) and exists,
    otherwise returns the English prompts directory.

    Args:
        base_dir: Base directory containing the prompts/ folder.
                 If None, uses the parent directory of prompts_pkg/

    Returns:
        Path to the prompts directory (may be localized)

    Examples:
        >>> get_prompts_dir()
        Path("/path/to/prompts")  # or prompts/zh-CN if PROMPT_LANGUAGE=zh-CN
    """
    # Determine base directory
    if base_dir is None:
        base_dir = Path(__file__).parent.parent / "prompts"
    else:
        base_dir = Path(base_dir) / "prompts"

    # Get language from environment
    language = os.environ.get("PROMPT_LANGUAGE", "zh-CN")

    # Return localized directory if it exists
    if language != "en":
        localized_dir = base_dir / language
        if localized_dir.exists() and localized_dir.is_dir():
            return localized_dir

    # Fall back to default
    return base_dir
