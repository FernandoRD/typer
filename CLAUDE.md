# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoTyper is a Python desktop app that simulates keyboard typing into any active OS window. Primary use case: remote server management (KVM over IP, iDRAC, iLO, serial consoles) where clipboard paste is unavailable. The app is structured as the `autotyper/` package; `typer.py` at the root is a backward-compatible shim.

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

Requires **Python 3.11+** (uses `enum.StrEnum`). There are no tests in this project.

## Architecture

```text
typer.py               — shim: from autotyper.__main__ import main
autotyper/
├── __init__.py        — package docstring only
├── __main__.py        — routes to run_headless() or TyperApp().mainloop()
├── config.py          — TRANSLATIONS, SPEED_PROFILES, StatusStyle(StrEnum), platform_mono_font()
├── markers.py         — Instruction TypeAlias, parse_instructions(), _MARKER_RE, _SPECIAL_KEYS
├── engine.py          — TypingEngine, TypingCallbacks (no tkinter dependency)
├── app.py             — TyperApp(ttk.Window) — all widgets here
└── cli.py             — parse_args(), run_headless()
```

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
- **Linux Wayland**: `pynput` does not work; the app detects `XDG_SESSION_TYPE=wayland` and shows a dismissible warning banner
