"""AI text generation via the Anthropic Claude API. No tkinter dependency.

The generator runs the API call on a daemon thread and streams the result back
through AICallbacks — the GUI is responsible for marshalling those callbacks
onto the main thread with `self.after(0, ...)`, exactly like TypingEngine.
"""

import json
import os
import pathlib
import threading
from collections.abc import Callable
from dataclasses import dataclass

from .config import ai_system_prompt, model_supports_adaptive

try:
    import anthropic
    _ANTHROPIC_AVAILABLE = True
except ImportError:
    _ANTHROPIC_AVAILABLE = False


# Claude Code / VS Code plugin store their browser-login OAuth token here.
_CLAUDE_CREDS   = pathlib.Path.home() / ".claude" / ".credentials.json"
# `ant auth login` (Anthropic CLI) stores its OAuth profile here.
_ANT_PROFILE_DIR = pathlib.Path.home() / ".config" / "anthropic"
# Beta header required when authenticating with an OAuth bearer token.
_OAUTH_BETA = "oauth-2025-04-20"


def is_available() -> bool:
    """True if the `anthropic` package is importable."""
    return _ANTHROPIC_AVAILABLE


def _env_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY")
                or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def _ant_profile() -> bool:
    return _ANT_PROFILE_DIR.is_dir()


def _claude_code_token() -> str | None:
    """The Claude Code browser-login OAuth access token, read fresh (Claude Code
    refreshes the file itself, so re-reading each call picks up new tokens)."""
    try:
        data = json.loads(_CLAUDE_CREDS.read_text())
        return data["claudeAiOauth"]["accessToken"] or None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def has_credentials() -> bool:
    """True if any supported credential source is present — an env key/token,
    an `ant auth login` profile, or the Claude Code browser login."""
    return _env_key() or _ant_profile() or _claude_code_token() is not None


def is_auth_error(e: Exception) -> bool:
    """True if the exception is an authentication failure (bad/expired credential)."""
    return _ANTHROPIC_AVAILABLE and isinstance(e, anthropic.AuthenticationError)


def build_client() -> "anthropic.Anthropic":
    """Resolve credentials the same way Claude Code / the Anthropic CLI do.

    Order: explicit env credentials → `ant auth login` profile (both resolved by
    the SDK) → the Claude Code / VS Code browser-login OAuth token. Nothing here
    is stored by AutoTyper.
    """
    if _env_key() or _ant_profile():
        return anthropic.Anthropic()          # SDK resolves env / ant profile
    token = _claude_code_token()
    if token:
        return anthropic.Anthropic(
            auth_token=token,
            default_headers={"anthropic-beta": _OAUTH_BETA},
        )
    return anthropic.Anthropic()              # nothing configured → raises on use


@dataclass
class AICallbacks:
    on_start: Callable[[], None] | None = None       # generation began
    on_text:  Callable[[str], None] | None = None    # a streamed text chunk
    on_done:  Callable[[str], None] | None = None     # (full_text)
    on_error: Callable[[Exception], None] | None = None


class AIGenerator:
    """Streams a Claude completion on a daemon thread via AICallbacks."""

    def __init__(self) -> None:
        self._active = False

    @property
    def is_generating(self) -> bool:
        return self._active

    def generate(self, prompt: str, lang: str, model: str,
                 callbacks: AICallbacks) -> None:
        """Start streaming a completion. Guards (lib/creds) are the caller's job."""
        self._active = True
        threading.Thread(
            target=self._run,
            args=(prompt, lang, model, callbacks),
            daemon=True,
        ).start()

    def _run(self, prompt: str, lang: str, model: str,
             callbacks: AICallbacks) -> None:
        try:
            client = build_client()          # env key / ant profile / Claude Code login
            if callbacks.on_start:
                callbacks.on_start()

            kwargs: dict = dict(
                model=model,
                max_tokens=8000,
                system=ai_system_prompt(lang),
                messages=[{"role": "user", "content": prompt}],
            )
            if model_supports_adaptive(model):   # Haiku 4.5 rejects adaptive thinking
                kwargs["thinking"] = {"type": "adaptive"}

            parts: list[str] = []
            with client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    parts.append(text)
                    if callbacks.on_text:
                        callbacks.on_text(text)

            if callbacks.on_done:
                callbacks.on_done("".join(parts))

        except Exception as e:
            if callbacks.on_error:
                callbacks.on_error(e)

        finally:
            self._active = False
