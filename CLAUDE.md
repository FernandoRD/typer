# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoTyper is a Python desktop app that simulates keyboard typing into any active OS window. Primary use case: remote server management (KVM over IP, iDRAC, iLO, serial consoles) where clipboard paste is unavailable. The app is structured as the `autotyper/` package; `typer.py` at the root is a backward-compatible shim.

An optional **AI assistant** uses an already-authenticated local provider CLI to draft text from a natural-language prompt when that provider passes its containment probe. It stays in a non-actionable preview until the user explicitly inserts it into the editor; only the normal typing action can use editor text.

## Running the App

```bash
# Activate venv first (Windows)
venv\Scripts\activate

# GUI mode (default) — both are equivalent
python typer.py
python -m autotyper

# With options
python typer.py --file script.txt --interval 50 --wait 3 --lang pt

# Headless (CLI) mode — no GUI, requires --file
python typer.py --headless --file script.txt --interval 80 --wait 3
```

## Dependencies

```bash
pip install -r requirements.txt
# ttkbootstrap>=1.20.0  pynput>=1.7.0
```

Requires **Python 3.11+** (uses `enum.StrEnum`). Tests live in `tests/`.

The AI assistant never reads API keys, token files, browser cookies, e-mails or credential paths. It only asks the local CLI whether it is already authenticated. Supported providers are Codex, Claude, and Google/Antigravity; each receives only its local allowlisted models. Codex and Google currently fail closed until their safe execution contracts are verified. There is no provider fallback.

## Architecture

```text
typer.py               — shim: from autotyper.__main__ import main
autotyper/
├── __init__.py        — package docstring only
├── __main__.py        — routes to run_headless() or TyperApp().mainloop()
├── config.py          — TRANSLATIONS, SPEED_PROFILES, StatusStyle(StrEnum), ModelInfo, preview normalization/validation, ai_system_prompt()
├── markers.py         — Instruction TypeAlias, parse_instructions(), _MARKER_RE, _SPECIAL_KEYS
├── drivers.py         — BaseKeyboardDriver, PynputDriver, EvdevDriver, get_keyboard_driver()
├── engine.py          — TypingEngine, TypingCallbacks (no tkinter dependency)
├── ai.py              — Provider, ProviderStatus, AIGenerator, AICallbacks, provider_status(), models_for() (no tkinter dependency)
├── vault.py           — BitwardenVault, VaultCallbacks, VaultItem, is_available() — Bitwarden `bw` CLI wrapper (no tkinter dependency)
├── app.py             — TyperApp(ttk.Window) + CollapsibleFrame — all widgets here
└── cli.py             — parse_args(), run_headless()
```

### UI layout

`CollapsibleFrame` (a small `ttk.Frame` subclass in `app.py`) wraps the **AI**, **Bitwarden**, and **Log** panels; all three start **collapsed** to keep the window compact. Its clickable `-link` header toggles `self.body` (where children are built); use `set_title()` for i18n, not `.configure(text=...)` — so `_refresh_ui_text()` calls `self._af/_bf/_log_frame.set_title(...)`.

**Packing order matters:** the footer cluster (status bar, log, progress bar, char counter) is packed `side="bottom"` in `__init__` *before* the text area — the only `expand=True` widget. So on shrink only the text area gives way; the footer keeps a fixed height and the status bar (packed first) is the last to be clipped, never hidden.

### AI assistant

`AIGenerator.generate(..., provider=Provider)` runs an isolated local CLI process on a daemon thread. `AICallbacks.on_text` is compatibility-only and receives the complete validated output once; `on_done(full)` receives that same complete output. The worker never touches Tk widgets; the GUI marshals callbacks through `self.after(0, ...)`.

The GUI refreshes `provider_status(provider)` asynchronously and uses only `models_for(provider)`. A stale probe response is discarded using a per-provider generation number. A Generate click schedules a fresh local probe instead of trusting a prior negative authentication result; a successful, current probe starts generation. No model is selected for an unavailable provider or one with no models, and generation stays disabled.

Generated text is normalized to LF and rendered only in a disabled preview. It is invalidated for a new request, provider/model change, cancellation, or error. **Insert generated output** is required to move it to the editor; it rejects `[[...]]` automation markers and unsafe Unicode control/format characters. The preview never triggers the keyboard driver.

### Bitwarden vault

An optional panel fetches credentials from a Bitwarden vault through the official **`bw` CLI** and types the selected item's password straight into the focused window. `vault.py` has no tkinter dependency and mirrors `ai.py`: every operation (`unlock`/`search`/`get_password`) runs on a daemon thread and reports back through `VaultCallbacks`, which the GUI marshals with `self.after(0, ...)`.

`vault.is_available()` is just `shutil.which("bw") is not None`; if `bw` isn't on PATH the panel stays visible but any action shows a clear error, and the rest of the app is unaffected (same graceful-degradation contract as the AI panel).

The GUI signs in directly with the supplied email and master password through `bw login --raw --nointeraction --passwordenv BW_PASSWORD`; it never accepts or passes 2FA codes, so no OTP is exposed on a process argv. The CLI itself supports non-interactive 2FA through `--method` and `--code`, but AutoTyper deliberately does not use those argv options; accounts with 2FA must complete an external Bitwarden/CLI flow first. The returned session is kept only in `BitwardenVault._session`. If the CLI is already authenticated externally, `VaultAlreadyLoggedInError` first validates `bw status`'s `userEmail` against the supplied email (case-insensitively) before selecting a `bw unlock` fallback, without calling `bw logout` or changing that external login. New-device verification likewise remains an external-flow limitation and is surfaced as a clear error.

Security contract: the master password is exchanged for a session token via `bw login --raw` (or an existing-login `bw unlock` fallback), kept **in memory only** (`BitwardenVault._session`) and never written to disk. Secrets (master password, session token) are passed to child processes through the **environment** (`BW_PASSWORD`/`BW_SESSION`), never on the argv, so they don't appear in the OS process list. `bw_type_password` types the fetched password directly via `TypingEngine` — it never lands in the editor, and its callbacks deliberately omit the char-count log lines so the secret never reaches the session log. The vault is locked (session dropped) on window close via `WM_DELETE_WINDOW` → `_on_close()`.

Requires the Bitwarden CLI installed separately (`npm install -g @bitwarden/cli`, native installer, or `winget install Bitwarden.CLI`) — it is **not** a pip dependency. Works with self-hosted/Vaultwarden servers via `bw config server` (configured in the CLI, outside AutoTyper).

### Threading model

Typing runs on a daemon thread. Two `threading.Event` objects in `TypingEngine` coordinate it:

| Event | Initial state | Meaning |
|---|---|---|
| `_stop_event` | cleared | `set()` = stop immediately |
| `_pause_event` | set | `set()` = running; `clear()` = paused |

**Rule**: widget values are read only in the main thread inside `start_typing_thread()`, then passed as plain arguments to `engine.start()`. The worker communicates back to the UI exclusively via `self.after(0, callback)`.

`_interruptible_sleep()` sleeps in ≤20ms chunks and returns `False` when `_stop_event` is set, keeping ESC/STOP latency under ~50ms.

### Typing modes

- **Normal** (`_type_all`) — types every instruction in a loop with progress updates
- **Chunk/line-by-line** (`_type_by_chunks`) — types one line, then blocks on a `pynput.Listener` waiting for ENTER or ESC

### Markers

Text can contain embedded markers that the engine interprets at runtime:

| Marker | Effect |
|---|---|
| `[[pause:N]]` | sleep N seconds (N must be > 0) |
| `[[speed:N]]` | change typing interval to N ms (N must be > 0) |
| `[[speed:reset]]` | restore base interval |
| `[[key:name]]` | press a special key or chord (`ctrl+c`, `F5`, `win`, etc.) |

`parse_instructions(text) → list[Instruction]` converts raw text into a flat instruction list. Markers with invalid or non-positive values are silently dropped.

A `[[key:...]]` chord (`_press_special_key` in `engine.py`) mixes modifiers with any special key or single character; unresolved parts are dropped. `_SPECIAL_KEYS` therefore carries common aliases (`del`, `pgup`, `pgdn`, `return`, `escape`, `ins`) — without the `del` alias, `ctrl+alt+del` would drop the Del key.

### Engine API contract

```python
engine.start(text, wait_s, interval_s, chunk_mode, callbacks)
```

`interval_s` is in **seconds** — callers must divide ms by 1000 before passing.

### i18n

Language switches at runtime without rebuilding the window. `_refresh_ui_text()` reconfigures every widget label in place. Adding a new string requires entries in both `TRANSLATIONS["en"]` and `TRANSLATIONS["pt"]` in `config.py`.

## ttkbootstrap Compatibility (>= 1.20.0)

`ScrolledText` is a compound widget (`Frame`) — it no longer inherits from `Text`. Always use `.text` to reach the inner widget:

```python
self._log_text.text.configure(state="normal")   # correct
self._log_text.text.insert("end", msg)
self._log_text.configure(state="normal")        # TclError — Frame has no state
```

Import path: `from ttkbootstrap.widgets.scrolled import ScrolledText`.

## Platform Notes

- **Windows**: fully supported; monospace font is Consolas
- **macOS**: supported; requires Accessibility permission for `pynput`; font is Menlo
- **Linux X11**: supported; font is Monospace
- **Linux Wayland**: fully supported via native `evdev` (`uinput`) driver; falls back to `pynput` if `/dev/uinput` is inaccessible (see `WAYLAND.md`)
