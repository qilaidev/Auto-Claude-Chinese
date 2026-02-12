import os

import core.auth as auth


def test_get_auth_token_ignores_whitespace_env(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "   ")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "\n\t")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "api-key-from-env")

    assert auth.get_auth_token() == "api-key-from-env"


def test_ensure_does_not_set_oauth_when_anthropic_auth_token_present(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "sk-test-third-party")
    monkeypatch.setattr(auth, "get_oauth_token", lambda: "oauth-should-not-be-used")

    auth.ensure_claude_code_oauth_token()

    assert os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") is None


def test_ensure_sets_oauth_when_no_anthropic_auth_token(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    # Make test deterministic even if developer has ~/.claude/settings.json
    monkeypatch.setattr(auth, "get_token_from_settings", lambda: (None, None))
    monkeypatch.setattr(auth, "get_oauth_token", lambda: "oauth-token")

    auth.ensure_claude_code_oauth_token()

    assert os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == "oauth-token"


def test_ensure_sets_oauth_when_existing_anthropic_auth_token_is_whitespace(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "   ")
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    monkeypatch.setattr(auth, "get_token_from_settings", lambda: (None, None))
    monkeypatch.setattr(auth, "get_oauth_token", lambda: "oauth-token")

    auth.ensure_claude_code_oauth_token()

    assert os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") == "oauth-token"
