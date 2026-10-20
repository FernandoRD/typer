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
import re
import shutil
import subprocess
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass

# Windows: keep the bw child process from flashing a console window.
_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0


class VaultLoggedOutError(RuntimeError):
    """Raised when a vault action needs an authenticated Bitwarden account."""


class VaultTwoFactorError(RuntimeError):
    """Raised when non-interactive login requires two-factor authentication."""


class VaultDeviceVerificationError(RuntimeError):
    """Raised when Bitwarden requires new-device verification."""


class VaultAlreadyLoggedInError(RuntimeError):
    """Raised only to select the safe unlock fallback for an existing login."""


class VaultLoggedInIdentityError(RuntimeError):
    """Raised when the externally logged-in account cannot be safely verified."""


@dataclass(frozen=True)
class VaultItem:
    """A single login entry: `id` addresses it in `bw get`, the rest is safe display metadata."""
    id: str
    name: str
    username: str
    has_password: bool = True
    passkey_count: int = 0
    has_totp: bool = False


@dataclass(frozen=True)
class PasskeyDetail:
    """Allowlisted, non-secret passkey details safe for GUI display."""
    credential_id: str = ""
    rp_id: str = ""
    user_handle: str = ""
    metadata: tuple[tuple[str, str], ...] = ()


def _passkey_entries(login: object) -> list[dict]:
    """Normalize version-dependent passkey containers to valid dictionaries."""
    if not isinstance(login, dict):
        return []
    entries = []
    for key in ("fido2Credentials", "passkey"):
        raw = login.get(key)
        if isinstance(raw, dict):
            raw = [raw]
        if isinstance(raw, list):
            entries.extend(entry for entry in raw if isinstance(entry, dict))
    return entries


def _passkey_count(login: object) -> int:
    """Return only a count of valid passkey objects; never retain their data."""
    return len(_passkey_entries(login))


def _passkey_details(login: object) -> list[PasskeyDetail]:
    """Extract an allowlist of display-safe fields from CLI passkey objects.

    In particular, this never copies private keys, encrypted key material,
    seeds, or arbitrary fields that a newer CLI might add.
    """
    field_names = {
        "name": "Name", "creationDate": "Created", "lastUsedDate": "Last used",
        "counter": "Counter", "discoverable": "Discoverable",
        "credentialType": "Type", "type": "Type", "keyAlgorithm": "Algorithm",
        "algorithm": "Algorithm",
    }
    def safe_text(value: object) -> str:
        return value if isinstance(value, str) else ""

    details = []
    for entry in _passkey_entries(login):
        metadata = tuple(
            (label, str(entry[key])) for key, label in field_names.items()
            if key in entry and isinstance(entry[key], (str, int, float, bool))
        )
        details.append(PasskeyDetail(
            credential_id=safe_text(entry.get("credentialId") or entry.get("id")),
            rp_id=safe_text(entry.get("rpId") or entry.get("relyingPartyId")),
            user_handle=safe_text(entry.get("userHandle") or entry.get("userName")),
            metadata=metadata,
        ))
    return details


def is_current_vault_epoch(is_unlocked: bool, current_epoch: int,
                           request_epoch: int) -> bool:
    """Whether an async vault response still belongs to the active session."""
    return is_unlocked and current_epoch == request_epoch


_MISSING_TOTP_ERROR = re.compile(
    r"\b(?:no|missing)\s+totp(?:\s+(?:secret|code))?\b"
    r"|\btotp(?:\s+\w+){0,3}\s+(?:is\s+)?(?:not\s+available|unavailable|not\s+found|not\s+configured)\b"
    r"|\b(?:does not|doesn't|doesnt)\s+have\s+(?:a\s+)?totp\b",
    re.IGNORECASE,
)


def is_missing_totp_error(error: Exception) -> bool:
    """Whether a CLI failure explicitly says the requested item has no TOTP."""
    return bool(_MISSING_TOTP_ERROR.search(str(error)))


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
        lower_msg = msg.lower()
        if "not logged in" in lower_msg:
            raise VaultLoggedOutError(msg)
        if "already logged in" in lower_msg:
            raise VaultAlreadyLoggedInError(msg)
        if "device verification" in lower_msg or "new device verification" in lower_msg:
            raise VaultDeviceVerificationError(msg)
        if "two-step" in lower_msg or "two factor" in lower_msg or "two-factor" in lower_msg:
            raise VaultTwoFactorError(msg)
        raise RuntimeError(msg)
    return proc.stdout.strip()


@dataclass
class VaultCallbacks:
    on_unlocked: Callable[[], None] | None = None          # unlock succeeded
    on_items:    Callable[[list[VaultItem]], None] | None = None  # search results
    on_password: Callable[[str], None] | None = None       # (password) fetched
    on_totp:     Callable[[str], None] | None = None       # (current OTP) fetched on demand
    on_passkey_details: Callable[[list[PasskeyDetail]], None] | None = None
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

    # -- authentication ----------------------------------------------------
    def unlock(self, email: str, master_password: str, callbacks: VaultCallbacks) -> None:
        """Log in non-interactively and retain only its in-memory session token.

        If the CLI is already logged in externally, use `unlock` instead without
        changing that external login.  This lets the GUI work in either state.
        """
        self._start(self._unlock_worker, email, master_password, callbacks)

    def _unlock_worker(self, email: str, master_password: str, cb: VaultCallbacks) -> None:
        try:
            env = {"BW_PASSWORD": master_password}
            login_args = [
                "login", email, "--raw", "--nointeraction", "--passwordenv", "BW_PASSWORD",
            ]
            try:
                token = _run_bw(login_args, env_extra=env)
            except VaultAlreadyLoggedInError:
                self._validate_logged_in_email(email)
                token = _run_bw(
                    ["unlock", "--raw", "--nointeraction", "--passwordenv", "BW_PASSWORD"],
                    env_extra=env,
                )
            if not token:
                raise RuntimeError("bw login/unlock returned no session token.")
            self._session = token
            if cb.on_unlocked:
                cb.on_unlocked()
        except Exception as e:
            if cb.on_error:
                cb.on_error(e)
        finally:
            self._busy = False

    @staticmethod
    def _validate_logged_in_email(email: str) -> None:
        """Refuse to unlock an external CLI login for a different account."""
        try:
            status = json.loads(_run_bw(["status"]))
            logged_in_email = status.get("userEmail") if isinstance(status, dict) else None
            logged_in_status = status.get("status") if isinstance(status, dict) else None
        except Exception as exc:
            raise VaultLoggedInIdentityError(
                "Unable to verify the account already signed in to Bitwarden.") from exc
        if logged_in_status not in {"locked", "unlocked"} or not isinstance(logged_in_email, str) or (
            logged_in_email.strip().casefold() != email.strip().casefold()
        ):
            raise VaultLoggedInIdentityError(
                "The Bitwarden CLI is signed in with a different or invalid account.")

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
            if not isinstance(data, list):
                raise RuntimeError("bw list items returned an invalid JSON document.")
            items = []
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                login = entry.get("login")
                if not isinstance(login, dict):
                    continue
                passkey_count = _passkey_count(login)
                has_password = bool(login.get("password"))
                has_totp = bool(login.get("totp"))
                if not entry.get("id") or not (has_password or has_totp or passkey_count):
                    continue
                # Do not copy password, TOTP seed, or any passkey fields into
                # application memory.  The booleans/count are display metadata.
                items.append(VaultItem(
                    id=entry["id"],
                    name=entry.get("name", "") or "(no name)",
                    username=login.get("username") or "",
                    has_password=has_password,
                    passkey_count=passkey_count,
                    has_totp=has_totp,
                ))
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

    # -- fetch TOTP --------------------------------------------------------
    def get_totp(self, item_id: str, callbacks: VaultCallbacks) -> None:
        """Fetch the current OTP for one item only when explicitly requested."""
        self._start(self._totp_worker, item_id, callbacks)

    def _totp_worker(self, item_id: str, cb: VaultCallbacks) -> None:
        try:
            if not self._session:
                raise RuntimeError("Vault is locked — unlock first.")
            totp = _run_bw(
                ["get", "totp", item_id],
                env_extra={"BW_SESSION": self._session},
            )
            if cb.on_totp:
                cb.on_totp(totp)
        except Exception as e:
            if cb.on_error:
                cb.on_error(e)
        finally:
            self._busy = False

    # -- fetch passkey details --------------------------------------------
    def get_passkey_details(self, item_id: str, callbacks: VaultCallbacks) -> None:
        """Fetch an item on demand and expose only allowlisted passkey metadata."""
        self._start(self._passkey_details_worker, item_id, callbacks)

    def _passkey_details_worker(self, item_id: str, cb: VaultCallbacks) -> None:
        try:
            if not self._session:
                raise RuntimeError("Vault is locked — unlock first.")
            raw = _run_bw(
                ["get", "item", item_id],
                env_extra={"BW_SESSION": self._session},
            )
            entry = json.loads(raw)
            if not isinstance(entry, dict):
                raise RuntimeError("bw get item returned an invalid JSON document.")
            details = _passkey_details(entry.get("login"))
            if cb.on_passkey_details:
                cb.on_passkey_details(details)
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
