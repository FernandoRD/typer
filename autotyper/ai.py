"""Safe AI text generation through already-authenticated local CLIs.

No credential files, cookies, or token environment variables are read here.
The provider CLI is solely responsible for its own authentication. Prompts are
sent on stdin, generation runs in an empty temporary directory, and callers
receive output only after the process exits successfully and its complete
machine-readable response has been validated.
"""

from __future__ import annotations

import enum
import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .config import ModelInfo, ai_system_prompt

_PROMPT_LIMIT = 64 * 1024
_OUTPUT_LIMIT = 2 * 1024 * 1024
_RESULT_LIMIT = 1024 * 1024
_GENERATION_TIMEOUT = 180.0
_PROBE_TIMEOUT = 5.0


class Provider(enum.StrEnum):
    CODEX = "codex"
    CLAUDE = "claude"
    GOOGLE = "google"


@dataclass(frozen=True)
class ProviderStatus:
    """Redacted provider state suitable for direct display in the GUI."""

    provider: Provider
    executable: str
    installed: bool
    authenticated: bool
    safe: bool
    available: bool
    message: str

    @property
    def detail(self) -> str:
        """Backward-compatible name for the redacted UI message."""

        return self.message


class AIError(RuntimeError):
    """A safe-to-display local provider error."""


class AIUnavailableError(AIError):
    pass


class AIAuthenticationError(AIError):
    pass


class AIOutputError(AIError):
    pass


class AITimeoutError(AIError):
    pass


class AICancelledError(AIError):
    pass


@dataclass(frozen=True)
class _ProviderSpec:
    executable: str
    help_args: tuple[str, ...]
    required_help: tuple[str, ...]
    models: tuple[ModelInfo, ...]


_SPECS: dict[Provider, _ProviderSpec] = {
    Provider.CODEX: _ProviderSpec(
        executable="codex",
        help_args=("exec", "--help"),
        required_help=(),
        models=(),
    ),
    Provider.CLAUDE: _ProviderSpec(
        executable="claude",
        help_args=("--help",),
        required_help=(
            "--print", "--no-session-persistence", "--tools", "--permission-mode",
            "dontAsk", "--permission-prompts", "none", "--strict-mcp-config",
            "--mcp-config", "--safe-mode", "--restricted", "--output-format", "json",
            "--disable-slash-commands", "--no-chrome", "--setting-sources",
            "--prompt-suggestions",
        ),
        models=(ModelInfo("default", "Default", False, ()),),
    ),
    # agy is intentionally status-only until both stdin prompting and a
    # machine-readable, non-generating authentication probe are documented.
    Provider.GOOGLE: _ProviderSpec(
        executable="agy",
        help_args=("--help",),
        required_help=(
            "--print", "--mode", "plan", "--output-format", "json", "--sandbox",
        ),
        models=(),
    ),
}


def models_for(
    provider: Provider | str = Provider.CLAUDE,
    status: ProviderStatus | None = None,
) -> list[ModelInfo]:
    """Return a provider's fallback only after a safe readiness probe."""

    selected = _provider(provider)
    readiness = status or provider_status(selected)
    if (readiness.provider is not selected
            or not readiness.safe or not readiness.available):
        return []
    return list(_SPECS[selected].models)


def list_models(
    provider: Provider | str = Provider.CLAUDE,
    status: ProviderStatus | None = None,
) -> list[ModelInfo]:
    """Compatibility alias for GUI code that previously queried an API."""

    return models_for(provider, status)


def is_available(provider: Provider | str = Provider.CLAUDE) -> bool:
    """True only when the provider passed every readiness check."""

    return provider_status(provider).available


def has_credentials(provider: Provider | str = Provider.CLAUDE) -> bool:
    """Detect login through the CLI without reading credential storage."""

    return provider_status(provider).authenticated


def is_auth_error(exc: Exception) -> bool:
    return isinstance(exc, AIAuthenticationError)


def provider_status(
    provider: Provider | str = Provider.CLAUDE,
    *,
    cancel_event: threading.Event | None = None,
    on_process: Callable[[subprocess.Popen[bytes] | None], None] | None = None,
) -> ProviderStatus:
    """Probe containment flags and authentication without making a model call."""

    selected = _provider(provider)
    spec = _SPECS[selected]
    executable = shutil.which(spec.executable)
    if executable is None:
        return ProviderStatus(selected, spec.executable, False, False, False, False,
                              f"{spec.executable} CLI is not installed")

    if selected is Provider.CODEX:
        return ProviderStatus(
            selected, spec.executable, True, False, False, False,
            "Codex is disabled until an official tool-free, no-read mode is available",
        )
    if selected is Provider.GOOGLE:
        return ProviderStatus(
            selected, spec.executable, True, False, False, False,
            "agy is disabled until safe stdin prompting and auth status are documented",
        )
    if os.name != "posix":
        return ProviderStatus(
            selected, spec.executable, True, False, False, False,
            "local AI generation is disabled on this platform",
        )

    try:
        help_result = _run_cli(
            [executable, *spec.help_args], stdin=b"", timeout=_PROBE_TIMEOUT,
            stdout_limit=256 * 1024, stderr_limit=64 * 1024,
            cancel_event=cancel_event, on_process=on_process,
        )
    except AICancelledError:
        raise
    except AIError as exc:
        return ProviderStatus(selected, spec.executable, True, False, False, False, str(exc))

    help_text = (help_result.stdout + help_result.stderr).decode("utf-8", "replace")
    missing = [flag for flag in spec.required_help if flag not in help_text]
    if missing:
        return ProviderStatus(selected, spec.executable, True, False, False, False,
                              "required containment flags are unavailable")

    try:
        authenticated = _probe_auth(
            selected, executable, cancel_event=cancel_event, on_process=on_process)
    except AICancelledError:
        raise
    except AIError as exc:
        return ProviderStatus(selected, spec.executable, True, False, True, False, str(exc))
    detail = "ready" if authenticated else "not authenticated"
    return ProviderStatus(
        selected, spec.executable, True, authenticated, True, authenticated, detail)


@dataclass
class AICallbacks:
    on_start: Callable[[], None] | None = None
    # Compatibility hook: invoked once with the complete validated result.
    on_text: Callable[[str], None] | None = None
    on_done: Callable[[str], None] | None = None
    on_error: Callable[[Exception], None] | None = None


class AIGenerator:
    """Run one isolated local CLI generation on a daemon thread."""

    def __init__(self, *, timeout: float = _GENERATION_TIMEOUT) -> None:
        self._timeout = timeout
        self._lock = threading.Lock()
        self._active = False
        self._cancel_event = threading.Event()
        self._process: subprocess.Popen[bytes] | None = None

    @property
    def is_generating(self) -> bool:
        with self._lock:
            return self._active

    def generate(
        self,
        prompt: str,
        lang: str,
        model: str,
        callbacks: AICallbacks,
        supports_adaptive: bool = False,
        effort: str | None = None,
        *,
        provider: Provider | str = Provider.CLAUDE,
    ) -> None:
        """Start generation; only a complete validated result reaches callbacks.

        ``supports_adaptive`` remains for source compatibility and is ignored.
        Provider/model/effort values are checked against local allowlists before
        becoming argv elements. The prompt itself is always written to stdin.
        """

        del supports_adaptive
        selected = _provider(provider)
        if selected is not Provider.CLAUDE:
            raise AIUnavailableError("this provider has no safe generation contract")
        if os.name != "posix":
            raise AIUnavailableError("local AI generation is disabled on this platform")
        encoded = _compose_prompt(prompt, lang).encode("utf-8")
        if not prompt.strip():
            raise ValueError("prompt must not be empty")
        if len(encoded) > _PROMPT_LIMIT:
            raise ValueError("prompt is too large")
        _validate_selection(selected, model, effort)

        with self._lock:
            if self._active:
                raise AIError("generation is already in progress")
            self._active = True
            self._cancel_event = threading.Event()

        threading.Thread(
            target=self._run,
            args=(selected, encoded, model, effort, callbacks),
            daemon=True,
            name="autotyper-ai",
        ).start()

    def cancel(self) -> bool:
        """Try to cancel before publication.

        ``True`` means cancellation won the publication lock, so ``on_text``
        and ``on_done`` will not run. ``False`` means the generator was idle or
        publication already won; already-dispatched result callbacks remain valid.
        """

        with self._lock:
            if not self._active:
                return False
            self._cancel_event.set()
            process = self._process
        if process is not None:
            _terminate_process(process)
        return True

    def _set_process(self, process: subprocess.Popen[bytes] | None) -> None:
        with self._lock:
            self._process = process

    def _commit_success(self) -> bool:
        """Atomically choose publication over cancellation."""

        with self._lock:
            if self._cancel_event.is_set():
                return False
            self._process = None
            self._active = False
            return True

    def _commit_error(self, exc: Exception) -> Exception:
        """Atomically finalize an error, letting an accepted cancel win."""

        with self._lock:
            cancelled = self._cancel_event.is_set()
            self._process = None
            self._active = False
        return AICancelledError("generation cancelled") if cancelled else exc

    def _run(
        self,
        provider: Provider,
        prompt: bytes,
        model: str,
        effort: str | None,
        callbacks: AICallbacks,
    ) -> None:
        try:
            status = provider_status(
                provider, cancel_event=self._cancel_event, on_process=self._set_process)
            if not status.installed or not status.available:
                if (status.installed and not status.authenticated
                        and status.detail == "not authenticated"):
                    raise AIAuthenticationError(status.detail)
                raise AIUnavailableError(status.detail)
            if callbacks.on_start:
                callbacks.on_start()

            executable = shutil.which(_SPECS[provider].executable)
            if executable is None:  # binary disappeared after the status probe
                raise AIUnavailableError("provider CLI is not installed")
            argv = _generation_argv(provider, executable, model, effort)
            result = _run_cli(
                argv,
                stdin=prompt,
                timeout=self._timeout,
                cancel_event=self._cancel_event,
                on_process=self._set_process,
            )
            text = _parse_result(provider, result.stdout)
            if not self._commit_success():
                raise AICancelledError("generation cancelled")
            if callbacks.on_text:
                callbacks.on_text(text)
            if callbacks.on_done:
                callbacks.on_done(text)
        except Exception as exc:
            safe_exc = exc if isinstance(exc, (AIError, ValueError)) else AIError(
                "local provider failed unexpectedly")
            safe_exc = self._commit_error(safe_exc)
            if callbacks.on_error:
                callbacks.on_error(safe_exc)


@dataclass(frozen=True)
class _ProcessResult:
    stdout: bytes
    stderr: bytes


def _run_cli(
    argv: Sequence[str],
    *,
    stdin: bytes,
    timeout: float,
    stdout_limit: int = _OUTPUT_LIMIT,
    stderr_limit: int = 128 * 1024,
    cancel_event: threading.Event | None = None,
    on_process: Callable[[subprocess.Popen[bytes] | None], None] | None = None,
) -> _ProcessResult:
    """Run a fixed argv with bounded pipes; never return partial output."""

    if timeout <= 0:
        raise ValueError("timeout must be positive")
    if os.name != "posix":
        raise AIUnavailableError("local AI subprocess isolation is unavailable on this platform")
    cancel_event = cancel_event or threading.Event()
    if cancel_event.is_set():
        raise AICancelledError("generation cancelled")
    with tempfile.TemporaryDirectory(prefix="autotyper-ai-") as cwd:
        try:
            process = subprocess.Popen(
                list(argv),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                shell=False,
                close_fds=True,
                cwd=cwd,
                env=_safe_env(),
                start_new_session=True,
            )
        except OSError as exc:
            raise AIUnavailableError("provider CLI could not be started") from exc

        if on_process:
            on_process(process)
        stdout = bytearray()
        stderr = bytearray()
        overflow = threading.Event()

        def read_pipe(pipe, target: bytearray, limit: int) -> None:
            try:
                while chunk := pipe.read(8192):
                    remaining = limit + 1 - len(target)
                    if remaining > 0:
                        target.extend(chunk[:remaining])
                    if len(target) > limit:
                        overflow.set()
            finally:
                pipe.close()

        readers = [
            threading.Thread(
                target=read_pipe, args=(process.stdout, stdout, stdout_limit), daemon=True),
            threading.Thread(
                target=read_pipe, args=(process.stderr, stderr, stderr_limit), daemon=True),
        ]
        for reader in readers:
            reader.start()

        def feed_stdin() -> None:
            try:
                process.stdin.write(stdin)
                process.stdin.flush()
            except (BrokenPipeError, OSError):
                pass
            finally:
                try:
                    process.stdin.close()
                except OSError:
                    pass

        feeder = threading.Thread(target=feed_stdin, daemon=True)
        feeder.start()
        deadline = time.monotonic() + timeout
        reason: str | None = None
        while process.poll() is None:
            if cancel_event.is_set():
                reason = "cancelled"
                break
            if overflow.is_set():
                reason = "overflow"
                break
            if time.monotonic() >= deadline:
                reason = "timeout"
                break
            time.sleep(0.02)

        # ``cancel()`` may terminate the process before this worker observes
        # the event inside the polling loop; cancellation still wins.
        if reason is None and cancel_event.is_set():
            reason = "cancelled"
        if reason:
            _terminate_process(process)
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
        feeder.join(timeout=1)
        for reader in readers:
            reader.join(timeout=1)
        if on_process:
            on_process(None)

        if reason == "cancelled":
            raise AICancelledError("generation cancelled")
        if reason == "timeout":
            raise AITimeoutError("local provider timed out")
        if reason == "overflow" or overflow.is_set():
            raise AIOutputError("local provider output exceeded the size limit")
        if process.returncode != 0:
            # Never surface provider stderr: it can echo a prompt, path, or
            # credential that no heuristic redactor can reliably recognize.
            detail = _sanitize_stderr(bytes(stderr)).lower()
            if any(marker in detail for marker in (
                "not logged in", "login required", "unauthorized", "authentication failed",
            )):
                raise AIAuthenticationError("provider authentication failed")
            raise AIError(f"local provider failed (exit {process.returncode})")
        return _ProcessResult(bytes(stdout), bytes(stderr))


def _safe_env() -> dict[str, str]:
    """Keep only process discovery, locale, and the CLI's auth-store location."""

    allowed = ("PATH", "HOME", "LANG", "LC_ALL", "LC_CTYPE", "SYSTEMROOT", "WINDIR")
    env = {name: os.environ[name] for name in allowed if name in os.environ}
    env["NO_COLOR"] = "1"
    env["TERM"] = "dumb"
    return env


def _probe_auth(
    provider: Provider,
    executable: str,
    *,
    cancel_event: threading.Event | None = None,
    on_process: Callable[[subprocess.Popen[bytes] | None], None] | None = None,
) -> bool:
    if provider is Provider.CLAUDE:
        result = _run_cli(
            [executable, "auth", "status", "--json"], stdin=b"", timeout=_PROBE_TIMEOUT,
            stdout_limit=64 * 1024, stderr_limit=64 * 1024,
            cancel_event=cancel_event, on_process=on_process,
        )
        try:
            payload = json.loads(result.stdout)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise AIOutputError("authentication status was not valid JSON") from exc
        return isinstance(payload, dict) and payload.get("loggedIn") is True
    return False


def _generation_argv(
    provider: Provider, executable: str, model: str, effort: str | None,
) -> list[str]:
    if provider is Provider.CLAUDE:
        argv = [
            executable, "--print", "--no-session-persistence", "--safe-mode", "--restricted",
            "--strict-mcp-config", "--mcp-config", "{}", "--tools", "",
            "--permission-mode", "dontAsk", "--permission-prompts", "none", "--no-chrome",
            "--disable-slash-commands", "--setting-sources", "", "--output-format", "json",
            "--prompt-suggestions=false",
        ]
        if model != "default":
            argv.extend(("--model", model))
        if effort:
            argv.extend(("--effort", effort))
        return argv
    raise AIUnavailableError("provider generation is disabled pending a safe contract")


def _parse_result(provider: Provider, raw: bytes) -> str:
    if len(raw) > _OUTPUT_LIMIT:
        raise AIOutputError("local provider output exceeded the size limit")
    try:
        decoded = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AIOutputError("local provider output was not UTF-8") from exc

    if provider is Provider.CLAUDE:
        try:
            payload = json.loads(decoded)
        except json.JSONDecodeError as exc:
            raise AIOutputError("Claude returned invalid JSON") from exc
        if not isinstance(payload, dict) or payload.get("type") != "result":
            raise AIOutputError("Claude returned an unexpected response")
        if payload.get("is_error") is not False or payload.get("subtype") != "success":
            raise AIOutputError("Claude did not complete successfully")
        text = payload.get("result")
    else:
        raise AIUnavailableError("provider output contract is not enabled")

    if not isinstance(text, str) or not text:
        raise AIOutputError("local provider returned no final text")
    if len(text.encode("utf-8")) > _RESULT_LIMIT:
        raise AIOutputError("generated text exceeded the size limit")
    return text


def _provider(provider: Provider | str) -> Provider:
    try:
        return provider if isinstance(provider, Provider) else Provider(provider)
    except ValueError as exc:
        raise ValueError("unknown AI provider") from exc


def _validate_selection(provider: Provider, model: str, effort: str | None) -> None:
    allowed_models = {info.id: info for info in _SPECS[provider].models}
    if model not in allowed_models:
        raise ValueError("model is not allowed for this provider")
    if effort is not None and effort not in allowed_models[model].effort_levels:
        raise ValueError("effort is not allowed for this model")


def _compose_prompt(prompt: str, lang: str) -> str:
    return f"{ai_system_prompt(lang)}\n\nUSER REQUEST:\n{prompt}"


_SECRET_VALUE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|refresh[_-]?token|authorization|password|secret)"
    r"(\s*[:=]\s*)([^\s,;]+)"
)
_TOKEN = re.compile(r"(?i)\b(?:sk-(?:ant-|proj-)?|ghp_|github_pat_|xox[baprs]-)[A-Za-z0-9_-]{8,}")


def _sanitize_stderr(raw: bytes) -> str:
    """Bound and redact diagnostics before they can reach UI/log callbacks."""

    text = raw[:16 * 1024].decode("utf-8", "replace")
    text = _SECRET_VALUE.sub(lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", text)
    text = _TOKEN.sub("[REDACTED]", text)
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        return ""
    return " ".join(lines[:3])[:512]


def _terminate_process(process: subprocess.Popen[bytes]) -> None:
    if os.name == "posix":
        group_exists = True
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except OSError:
            group_exists = False
        if group_exists:
            time.sleep(0.5)
        # The leader may exit while a child remains in the process group.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            pass
        return

    if process.poll() is None:  # unreachable for AI generation: Windows is fail-closed
        process.terminate()
        try:
            process.wait(timeout=0.5)
        except (OSError, subprocess.TimeoutExpired):
            process.kill()
