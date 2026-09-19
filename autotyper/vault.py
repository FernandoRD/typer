"""Bitwarden vault integration via the official `bw` CLI. No tkinter dependency.

Credentials are fetched by shelling out to the Bitwarden CLI, which owns all the
encryption, session handling and sync. AutoTyper never stores a credential: the
master password is used only to obtain a session token, and neither the password
nor the token nor any fetched secret is written to disk or to the session log.

Like AIGenerator and TypingEngine, every operation runs on a daemon thread and
reports back through VaultCallbacks — the GUI marshals those callbacks onto the
main thread with `self.after(0, ...)`. The worker never touches widgets.

Secrets are passed to child processes through the environment (BW_PASSWORD /
BW_SESSION), never on the argv, so they don't show up in the OS process list.
"""

import json
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

# Windows: keep the bw child process from flashing a console window.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


class VaultLoggedOutError(RuntimeError):
    """Raised when a vault action fails because no Bitwarden account is logged
    in. AutoTyper only does `unlock`; the user must run `bw login` themselves
    first. The GUI maps this to an actionable message telling them to do so."""


@dataclass(frozen=True)
class VaultItem:
    """A single login entry: `id` addresses it in `bw get`, the rest is display."""
    id: str
    name: str
    username: str


def is_available() -> bool:
    """True if the Bitwarden `bw` CLI is on PATH."""
    return shutil.which("bw") is not None


def _bw_path() -> str | None:
    return shutil.which("bw")


def _run_bw(args: list[str], env_extra: dict[str, str] | None = None,
            timeout: float = 60.0) -> str:
    """Run `bw <args>` and return stdout (stripped). Secrets go in `env_extra`,
    which is merged into the child environment only — never onto the argv.

    Raises RuntimeError with the CLI's stderr on a non-zero exit.
    """
    bw = _bw_path()
    if bw is None:
        raise RuntimeError("Bitwarden CLI ('bw') not found on PATH.")

    import os
    env = os.environ.copy()
    if env_extra:
        env.update(env_extra)

    proc = subprocess.run(
        [bw, *args],
        capture_output=True, text=True, env=env,
        timeout=timeout, creationflags=_NO_WINDOW,
    )
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip() or f"bw exited {proc.returncode}"
        # bw prints "You are not logged in." (English regardless of locale) when
        # no account is authenticated — surface it as a distinct, actionable type.
        if "not logged in" in msg.lower():
            raise VaultLoggedOutError(msg)
        raise RuntimeError(msg)
    return proc.stdout.strip()


@dataclass
class VaultCallbacks:
    on_unlocked: Callable[[], None] | None = None          # unlock succeeded
    on_items:    Callable[[list[VaultItem]], None] | None = None  # search results
    on_password: Callable[[str], None] | None = None       # (password) fetched
    on_locked:   Callable[[], None] | None = None          # session cleared
    on_error:    Callable[[Exception], None] | None = None


class BitwardenVault:
    """Talks to the Bitwarden CLI on daemon threads via VaultCallbacks.

    Holds the unlock session token in memory only (never persisted). All the
    credential guards (is bw installed?) are the caller's job.
    """

    def __init__(self) -> None:
        self._session: str | None = None
        self._busy = False

    @property
    def is_unlocked(self) -> bool:
        return self._session is not None

    @property
    def is_busy(self) -> bool:
        return self._busy

    def _start(self, target, *args) -> None:
        self._busy = True
        threading.Thread(target=target, args=args, daemon=True).start()

    # -- unlock ------------------------------------------------------------
    def unlock(self, master_password: str, callbacks: VaultCallbacks) -> None:
        """Exchange the master password for a session token (kept in memory)."""
        self._start(self._unlock_worker, master_password, callbacks)

    def _unlock_worker(self, master_password: str, cb: VaultCallbacks) -> None:
        try:
            token = _run_bw(
                ["unlock", "--raw", "--passwordenv", "BW_PASSWORD"],
                env_extra={"BW_PASSWORD": master_password},
            )
            if not token:
                raise RuntimeError("bw unlock returned no session token.")
            self._session = token
            if cb.on_unlocked:
                cb.on_unlocked()
        except Exception as e:
            if cb.on_error:
                cb.on_error(e)
        finally:
            self._busy = False

    # -- search ------------------------------------------------------------
    def search(self, query: str, callbacks: VaultCallbacks) -> None:
        """List login items matching `query`. Requires a prior unlock."""
        self._start(self._search_worker, query, callbacks)

    def _search_worker(self, query: str, cb: VaultCallbacks) -> None:
        try:
            if not self._session:
                raise RuntimeError("Vault is locked — unlock first.")
            raw = _run_bw(
                ["list", "items", "--search", query],
                env_extra={"BW_SESSION": self._session},
            )
            data = json.loads(raw) if raw else []
            items = [
                VaultItem(
                    id=entry.get("id", ""),
                    name=entry.get("name", "") or "(no name)",
                    username=((entry.get("login") or {}).get("username") or ""),
                )
                for entry in data
                if entry.get("id") and (entry.get("login") or {}).get("password")
            ]
            if cb.on_items:
                cb.on_items(items)
        except Exception as e:
            if cb.on_error:
                cb.on_error(e)
        finally:
            self._busy = False

    # -- fetch password ----------------------------------------------------
    def get_password(self, item_id: str, callbacks: VaultCallbacks) -> None:
        """Fetch the password for one item. Requires a prior unlock."""
        self._start(self._password_worker, item_id, callbacks)

    def _password_worker(self, item_id: str, cb: VaultCallbacks) -> None:
        try:
            if not self._session:
                raise RuntimeError("Vault is locked — unlock first.")
            password = _run_bw(
                ["get", "password", item_id],
                env_extra={"BW_SESSION": self._session},
            )
            if cb.on_password:
                cb.on_password(password)
        except Exception as e:
            if cb.on_error:
                cb.on_error(e)
        finally:
            self._busy = False

    # -- lock --------------------------------------------------------------
    def lock(self, callbacks: VaultCallbacks | None = None) -> None:
        """Drop the in-memory session and lock the CLI vault. Runs synchronously
        (fast, and safe to call on shutdown)."""
        token, self._session = self._session, None
        if token:
            try:
                _run_bw(["lock"], env_extra={"BW_SESSION": token}, timeout=15.0)
            except Exception:
                pass  # session already dropped locally; best-effort remote lock
        if callbacks and callbacks.on_locked:
            callbacks.on_locked()
