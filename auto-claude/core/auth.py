"""
Authentication helpers for Auto Claude.
Auto Claude 认证辅助模块。

=== 本地特色：直接调用本地已认证的 Claude ===

本模块是 Auto-Claude-Chinese 的核心特色之一。
无需额外配置 API Key，直接复用本地 claude CLI 的认证状态。

Provides centralized authentication token resolution with fallback support
for multiple sources including:
- Environment variables (环境变量)
- Claude Code settings.json (third-party auth tokens, 第三方认证)
- macOS Keychain (official OAuth, 官方 OAuth)

Credential Priority Order (认证优先级，从高到低):
1. Environment variables (CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_AUTH_TOKEN, ANTHROPIC_API_KEY)
   环境变量 - 最高优先级
2. ~/.claude/settings.json (third-party auth like yunyi)
   第三方渠道配置（如云翼），支持 ANTHROPIC_AUTH_TOKEN 或 ANTHROPIC_API_KEY
3. macOS Keychain (official Claude Code OAuth)
   macOS 钥匙串（官方 OAuth 自动存储）

This design ensures third-party activation channels work reliably.
此设计确保第三方激活渠道可靠工作，用户无需手动管理 API Key。
"""

import json
import os
import platform
import subprocess
from pathlib import Path

# Priority order for auth token resolution
AUTH_TOKEN_ENV_VARS = [
    "CLAUDE_CODE_OAUTH_TOKEN",  # OAuth token from Claude Code CLI
    "ANTHROPIC_AUTH_TOKEN",  # CCR/proxy token (for enterprise/third-party setups)
    "ANTHROPIC_API_KEY",  # 云翼等第三方渠道使用的 API Key
]

# Environment variables to pass through to SDK subprocess
SDK_ENV_VARS = [
    "ANTHROPIC_BASE_URL",
    "ANTHROPIC_AUTH_TOKEN",
    "ANTHROPIC_API_KEY",  # 云翼等第三方渠道
    "CLAUDE_CODE_OAUTH_TOKEN",
    "NO_PROXY",
    "DISABLE_TELEMETRY",
    "DISABLE_COST_WARNINGS",
    "API_TIMEOUT_MS",
]

# Claude Code settings file path
CLAUDE_SETTINGS_PATH = Path.home() / ".claude" / "settings.json"


def get_token_from_keychain() -> str | None:
    """
    Get authentication token from macOS Keychain.

    Only works on macOS. Returns None on other platforms or if not found.
    """
    if platform.system() != "Darwin":
        return None

    try:
        result = subprocess.run(
            ["/usr/bin/security", "find-generic-password", "-s",
             "Claude Code-credentials", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None

        credentials_json = result.stdout.strip()
        if not credentials_json:
            return None

        data = json.loads(credentials_json)
        token = data.get("claudeAiOauth", {}).get("accessToken")
        return token if token else None

    except (subprocess.TimeoutExpired, json.JSONDecodeError, Exception):
        return None


def get_token_from_settings() -> tuple[str | None, str | None]:
    """
    Get auth token and base URL from ~/.claude/settings.json.

    This supports third-party activation channels (like yunyi) that store
    credentials in the Claude Code settings file.

    Returns:
        Tuple of (token, base_url) - either or both may be None
    """
    if not CLAUDE_SETTINGS_PATH.exists():
        return None, None

    try:
        with open(CLAUDE_SETTINGS_PATH, encoding="utf-8") as f:
            settings = json.load(f)

        env_settings = settings.get("env", {})
        # 优先 ANTHROPIC_AUTH_TOKEN，其次 ANTHROPIC_API_KEY（云翼等第三方渠道）
        token = env_settings.get("ANTHROPIC_AUTH_TOKEN") or env_settings.get("ANTHROPIC_API_KEY")
        base_url = env_settings.get("ANTHROPIC_BASE_URL")

        return token, base_url

    except (OSError, json.JSONDecodeError, Exception):
        return None, None


def get_auth_token() -> str | None:
    """
    Get authentication token from multiple sources.

    Priority order:
    1. Environment variables (CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_AUTH_TOKEN)
    2. ~/.claude/settings.json (third-party auth)
    3. macOS Keychain (official OAuth)

    Returns:
        Token string if found, None otherwise
    """
    # 1. Check environment variables first
    for var in AUTH_TOKEN_ENV_VARS:
        token = os.environ.get(var)
        if token:
            return token

    # 2. Check ~/.claude/settings.json (third-party auth)
    settings_token, _ = get_token_from_settings()
    if settings_token:
        return settings_token

    # 3. Fallback to macOS Keychain
    return get_token_from_keychain()


def get_oauth_token() -> str | None:
    """Get the Claude Code OAuth token (not ANTHROPIC_AUTH_TOKEN)."""
    token = os.environ.get("CLAUDE_CODE_OAUTH_TOKEN")
    if token:
        return token

    return get_token_from_keychain()


def get_anthropic_auth_token() -> str | None:
    """Get the ANTHROPIC_AUTH_TOKEN from env or settings.json."""
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if token:
        return token

    settings_token, _ = get_token_from_settings()
    return settings_token


def get_auth_token_source() -> str | None:
    """Get the name of the source that provided the auth token."""
    # Check environment variables first
    for var in AUTH_TOKEN_ENV_VARS:
        if os.environ.get(var):
            return f"env:{var}"

    # Check settings.json
    settings_token, _ = get_token_from_settings()
    if settings_token:
        return "~/.claude/settings.json"

    # Check macOS Keychain
    if get_token_from_keychain():
        return "macOS Keychain"

    return None


def require_auth_token() -> str:
    """
    Get authentication token or raise ValueError with diagnostic info.
    """
    token = get_auth_token()
    if not token:
        error_msg = (
            "未找到认证凭证。\n\n"
            "已检查的凭证来源（按优先级）：\n"
            "  1. 环境变量: CLAUDE_CODE_OAUTH_TOKEN, ANTHROPIC_AUTH_TOKEN\n"
            f"  2. 配置文件: {CLAUDE_SETTINGS_PATH}\n"
            "  3. macOS Keychain\n\n"
            "解决方案：\n"
            "  - 第三方渠道: 确保 ~/.claude/settings.json 包含有效的 ANTHROPIC_AUTH_TOKEN\n"
            "  - 官方 OAuth: 运行 'claude setup-token'\n"
            "  - 环境变量: 在 .env 中设置 ANTHROPIC_AUTH_TOKEN"
        )
        raise ValueError(error_msg)
    return token


def get_sdk_env_vars() -> dict[str, str]:
    """
    Get environment variables to pass to SDK subprocess.

    Merges variables from:
    1. Current environment
    2. ~/.claude/settings.json (third-party auth)
    """
    env = {}

    # First load from settings.json (lower priority)
    settings_token, settings_base_url = get_token_from_settings()
    if settings_token:
        env["ANTHROPIC_AUTH_TOKEN"] = settings_token
    if settings_base_url:
        env["ANTHROPIC_BASE_URL"] = settings_base_url

    # Then override with current environment (higher priority)
    for var in SDK_ENV_VARS:
        value = os.environ.get(var)
        if value:
            env[var] = value

    return env


def ensure_claude_code_oauth_token() -> None:
    """
    Ensure auth environment variables are set for SDK compatibility.

    Loads credentials from settings.json if not already in environment.
    """
    # Load from settings.json if needed
    settings_token, settings_base_url = get_token_from_settings()

    if not os.environ.get("ANTHROPIC_AUTH_TOKEN") and settings_token:
        os.environ["ANTHROPIC_AUTH_TOKEN"] = settings_token

    if not os.environ.get("ANTHROPIC_BASE_URL") and settings_base_url:
        os.environ["ANTHROPIC_BASE_URL"] = settings_base_url

    # Also set CLAUDE_CODE_OAUTH_TOKEN for SDK compatibility.
    # IMPORTANT: if third-party auth is present, do NOT auto-populate OAuth,
    # otherwise downstream code/CLI may prefer OAuth and fail.
    if not os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") and not os.environ.get(
        "ANTHROPIC_AUTH_TOKEN"
    ):
        oauth_token = get_oauth_token()
        if oauth_token:
            os.environ["CLAUDE_CODE_OAUTH_TOKEN"] = oauth_token


def diagnose_auth() -> str:
    """
    Diagnose authentication configuration and return status report.
    """
    lines = ["认证诊断报告:", "=" * 40]

    # Check environment variables
    for var in AUTH_TOKEN_ENV_VARS:
        val = os.environ.get(var)
        status = f"✓ 已设置 ({len(val)} 字符)" if val else "✗ 未设置"
        lines.append(f"  {var}: {status}")

    # Check settings.json
    token, base_url = get_token_from_settings()
    lines.append("\n~/.claude/settings.json:")
    lines.append(f"  ANTHROPIC_AUTH_TOKEN: {'✓ 已设置' if token else '✗ 未设置'}")
    lines.append(f"  ANTHROPIC_BASE_URL: {base_url or '✗ 未设置'}")

    # Check Keychain
    keychain_token = get_token_from_keychain()
    lines.append(f"\nmacOS Keychain: {'✓ 已设置' if keychain_token else '✗ 未设置'}")

    # Final status
    final_token = get_auth_token()
    source = get_auth_token_source()
    lines.append(f"\n最终状态: {'✓ 认证可用' if final_token else '✗ 认证失败'}")
    if source:
        lines.append(f"凭证来源: {source}")

    return "\n".join(lines)
