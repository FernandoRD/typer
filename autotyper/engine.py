"""TypingCallbacks dataclass and TypingEngine class — no tkinter dependency."""

import datetime
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from .drivers import BaseKeyboardDriver, get_keyboard_driver
from .markers import parse_instructions, Instruction


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

    def __init__(self, driver: BaseKeyboardDriver | None = None) -> None:
        if driver is not None:
            self._driver = driver
            self.driver_name = getattr(driver, "name", "custom")
        else:
            self._driver, self.driver_name = get_keyboard_driver()

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

    def close(self) -> None:
        """Release driver resources."""
        if hasattr(self, "_driver") and self._driver:
            self._driver.close()

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

    # ------------------------------------------------------------------
    # Worker thread entry point
    # ------------------------------------------------------------------

    def _run(self, text: str, wait_s: float, interval_s: float,
             chunk_mode: bool, callbacks: TypingCallbacks) -> None:
        instructions = parse_instructions(text)
        total        = sum(1 for op, _ in instructions if op == 'char')
        chars_done   = 0

        def on_esc():
            if callbacks.on_stop_requested:
                callbacks.on_stop_requested()
            else:
                self.stop()

        listener = self._driver.start_esc_listener(on_esc)

        dt = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if callbacks.on_session_start:
            callbacks.on_session_start(dt, total)

        try:
            if callbacks.on_waiting:
                callbacks.on_waiting(wait_s)
            if not self._interruptible_sleep(wait_s):
                return

            if chunk_mode:
                chars_done = self._type_by_chunks(instructions, interval_s, on_esc, callbacks)
            else:
                chars_done = self._type_all(instructions, interval_s, total, callbacks)

        except Exception as e:
            if callbacks.on_error:
                callbacks.on_error(e)

        finally:
            if hasattr(listener, "stop"):
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
                self._driver.type_char(str(val))
                chars_done += 1
                if chars_done % update_every == 0 or chars_done == total:
                    if callbacks.on_progress:
                        callbacks.on_progress(chars_done, total)
                if not self._interruptible_sleep(current_interval):
                    break
            elif op == 'pause':
                if not self._interruptible_sleep(float(val)):  # type: ignore[arg-type]
                    break
            elif op == 'speed':
                current_interval = (float(val) / 1000.0) if val is not None else base_interval
            elif op == 'key':
                if not self._wait_if_paused():
                    break
                self._driver.press_special_key(str(val))

        return chars_done

    def _type_by_chunks(self, instructions: list[Instruction], base_interval: float,
                        on_esc: Callable[[], None], callbacks: TypingCallbacks) -> int:
        """Type one line at a time, waiting for ENTER between lines."""
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
                    self._driver.type_char(str(val))
                    chars_done += 1
                    if not self._interruptible_sleep(current_interval):
                        return chars_done
                elif op == 'pause':
                    if not self._interruptible_sleep(float(val)):  # type: ignore[arg-type]
                        return chars_done
                elif op == 'speed':
                    current_interval = (float(val) / 1000.0) if val is not None else base_interval
                elif op == 'key':
                    if not self._wait_if_paused():
                        return chars_done
                    self._driver.press_special_key(str(val))

            if self._stop_event.is_set():
                break

            if callbacks.on_chunk_done:
                callbacks.on_chunk_done(i, total_lines)

            if i < total_lines:
                if not self._driver.wait_for_enter_or_esc(on_esc, self._stop_event):
                    break
                self._driver.tap_enter()
                chars_done += 1

        return chars_done
