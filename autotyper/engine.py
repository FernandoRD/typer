"""TypingCallbacks dataclass and TypingEngine class — no tkinter dependency."""

import datetime
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from pynput.keyboard import Controller, Key, Listener

from .markers import parse_instructions, _SPECIAL_KEYS, Instruction


@dataclass
class TypingCallbacks:
    on_session_start:  Callable[[str, int], None] | None = None   # (dt_str, total_chars)
    on_progress:       Callable[[int, int], None] | None = None   # (done, total)
    on_waiting:        Callable[[float], None] | None = None      # (wait_s)
    on_chunk_done:     Callable[[int, int], None] | None = None   # (cur_line, total_lines)
    on_done:           Callable[[bool, int, int], None] | None = None  # (stopped, done, total)
    on_error:          Callable[[Exception], None] | None = None
    on_stop_requested: Callable[[], None] | None = None


class TypingEngine:
    """Runs the typing worker thread; communicates back via TypingCallbacks."""

    def __init__(self) -> None:
        self._keyboard     = Controller()
        self._stop_event   = threading.Event()
        self._pause_event  = threading.Event()
        self._pause_event.set()          # set = running; clear = paused
        self._active       = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @property
    def is_typing(self) -> bool:
        return self._active

    @property
    def is_paused(self) -> bool:
        return not self._pause_event.is_set()

    def start(self, text: str, wait_s: float, interval_s: float,
              chunk_mode: bool, callbacks: TypingCallbacks) -> None:
        """Start the typing worker in a daemon thread. interval_s is in seconds."""
        self._stop_event.clear()
        self._pause_event.set()
        self._active = True
        threading.Thread(
            target=self._run,
            args=(text, wait_s, interval_s, chunk_mode, callbacks),
            daemon=True,
        ).start()

    def stop(self) -> None:
        """Signal the worker to stop as soon as possible."""
        if not self._stop_event.is_set():
            self._stop_event.set()
            self._pause_event.set()    # unblock pause so the thread can exit

    def toggle_pause(self) -> bool:
        """Toggle pause/resume. Returns True if now paused."""
        if self._pause_event.is_set():   # running → pause
            self._pause_event.clear()
            return True
        else:                            # paused → resume
            self._pause_event.set()
            return False

    # ------------------------------------------------------------------
    # Private helpers (run on worker thread)
    # ------------------------------------------------------------------

    def _wait_if_paused(self) -> bool:
        """Block while paused. Return False immediately if stop is requested."""
        while not self._pause_event.is_set():
            if self._stop_event.is_set():
                return False
            time.sleep(0.05)
        return not self._stop_event.is_set()

    def _interruptible_sleep(self, seconds: float) -> bool:
        """Sleep in small chunks, honouring stop and pause. Returns False if stopped."""
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if self._stop_event.is_set():
                return False
            if not self._pause_event.is_set():
                # Paused — spin without consuming the sleep budget
                time.sleep(0.05)
                continue
            remaining = end - time.monotonic()
            time.sleep(min(0.02, max(0.0, remaining)))
        return not self._stop_event.is_set()

    def _press_special_key(self, key_spec: str) -> None:
        """Press a single special key or chord (e.g. 'ctrl+c', 'F5', 'win')."""
        parts = [p.strip().lower() for p in key_spec.split('+')]

        def resolve(name: str):
            k = _SPECIAL_KEYS.get(name)
            if k is not None:
                return k
            if len(name) == 1:   # plain character key (e.g. 'c' in ctrl+c)
                return name
            return None

        keys = [k for k in (resolve(p) for p in parts) if k is not None]
        if not keys:
            return
        if len(keys) == 1:
            self._keyboard.tap(keys[0])
        else:
            held: list = []
            try:
                for k in keys[:-1]:
                    self._keyboard.press(k)
                    held.append(k)
                self._keyboard.tap(keys[-1])
            finally:
                for k in reversed(held):
                    self._keyboard.release(k)

    # ------------------------------------------------------------------
    # Worker thread entry point
    # ------------------------------------------------------------------

    def _run(self, text: str, wait_s: float, interval_s: float,
             chunk_mode: bool, callbacks: TypingCallbacks) -> None:
        instructions = parse_instructions(text)
        total        = sum(1 for op, _ in instructions if op == 'char')
        chars_done   = 0

        def on_esc(key):
            if key == Key.esc:
                if callbacks.on_stop_requested:
                    callbacks.on_stop_requested()
                else:
                    self.stop()
                return False

        listener = Listener(on_press=on_esc)
        listener.start()

        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if callbacks.on_session_start:
            callbacks.on_session_start(dt, total)

        try:
            if callbacks.on_waiting:
                callbacks.on_waiting(wait_s)
            if not self._interruptible_sleep(wait_s):
                return

            if chunk_mode:
                chars_done = self._type_by_chunks(instructions, interval_s, callbacks)
            else:
                chars_done = self._type_all(instructions, interval_s, total, callbacks)

        except Exception as e:
            if callbacks.on_error:
                callbacks.on_error(e)

        finally:
            listener.stop()
            self._active = False
            stopped = self._stop_event.is_set()
            if callbacks.on_done:
                callbacks.on_done(stopped, chars_done, total)

    # ------------------------------------------------------------------
    # Typing modes
    # ------------------------------------------------------------------

    def _type_all(self, instructions: list[Instruction], base_interval: float,
                  total: int, callbacks: TypingCallbacks) -> int:
        """Type every character, honouring [[pause:N]] and [[speed:N]] markers."""
        chars_done       = 0
        current_interval = base_interval
        update_every     = max(5, total // 200)

        for op, val in instructions:
            if op == 'char':
                if not self._wait_if_paused():
                    break
                if val == "\n":
                    self._keyboard.tap(Key.enter)
                else:
                    self._keyboard.type(val)
                chars_done += 1
                if chars_done % update_every == 0 or chars_done == total:
                    if callbacks.on_progress:
                        callbacks.on_progress(chars_done, total)
                if not self._interruptible_sleep(current_interval):
                    break
            elif op == 'pause':
                if not self._interruptible_sleep(val):
                    break
            elif op == 'speed':
                current_interval = (val / 1000.0) if val is not None else base_interval
            elif op == 'key':
                if not self._wait_if_paused():
                    break
                self._press_special_key(val)

        return chars_done

    def _type_by_chunks(self, instructions: list[Instruction], base_interval: float,
                        callbacks: TypingCallbacks) -> int:
        """Type one line at a time, waiting for ENTER between lines."""
        # Split instruction list into per-line groups on ('char', '\n')
        lines: list[list[Instruction]] = []
        current: list[Instruction] = []
        for op, val in instructions:
            if op == 'char' and val == '\n':
                lines.append(current)
                current = []
            else:
                current.append((op, val))
        lines.append(current)

        total_lines      = len(lines)
        chars_done       = 0
        current_interval = base_interval

        for i, line_ops in enumerate(lines, start=1):
            for op, val in line_ops:
                if op == 'char':
                    if not self._wait_if_paused():
                        return chars_done
                    self._keyboard.type(val)
                    chars_done += 1
                    if not self._interruptible_sleep(current_interval):
                        return chars_done
                elif op == 'pause':
                    if not self._interruptible_sleep(val):
                        return chars_done
                elif op == 'speed':
                    current_interval = (val / 1000.0) if val is not None else base_interval
                elif op == 'key':
                    if not self._wait_if_paused():
                        return chars_done
                    self._press_special_key(val)

            if self._stop_event.is_set():
                break

            if callbacks.on_chunk_done:
                callbacks.on_chunk_done(i, total_lines)

            if i < total_lines:
                if not self._wait_for_enter_or_esc(callbacks):
                    break
                self._keyboard.tap(Key.enter)
                chars_done += 1

        return chars_done

    def _wait_for_enter_or_esc(self, callbacks: TypingCallbacks) -> bool:
        """Block until ENTER (True) or ESC (False) is pressed."""
        proceed = threading.Event()
        result  = [True]

        def on_key(key):
            if key == Key.enter:
                result[0] = True
                proceed.set()
                return False
            if key == Key.esc:
                result[0] = False
                if callbacks.on_stop_requested:
                    callbacks.on_stop_requested()
                else:
                    self.stop()
                proceed.set()
                return False

        with Listener(on_press=on_key):
            proceed.wait()

        return result[0]
