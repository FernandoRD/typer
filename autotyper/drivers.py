"""Keyboard drivers for AutoTyper — abstract interface with pynput and evdev backends."""

from __future__ import annotations

import os
import select
import sys
import threading
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from .markers import _SPECIAL_KEYS


class BaseKeyboardDriver(ABC):
    """Abstract interface for typing simulation and global key monitoring."""

    @abstractmethod
    def type_char(self, char: str) -> None:
        """Type a single character."""

    @abstractmethod
    def tap_enter(self) -> None:
        """Tap the Enter key."""

    @abstractmethod
    def press_special_key(self, key_spec: str) -> None:
        """Press a special key or chord (e.g. 'ctrl+c', 'F5', 'win')."""

    @abstractmethod
    def start_esc_listener(self, on_esc: Callable[[], None]) -> Any:
        """Start a background listener that calls on_esc when ESC is pressed. Returns handle with stop()."""

    @abstractmethod
    def wait_for_enter_or_esc(self, on_esc: Callable[[], None], stop_event: threading.Event) -> bool:
        """Block until ENTER (returns True) or ESC (calls on_esc and returns False)."""

    def close(self) -> None:
        """Clean up driver resources."""
        pass


class PynputDriver(BaseKeyboardDriver):
    """Keyboard driver using pynput (X11, Windows, macOS)."""

    def __init__(self) -> None:
        from pynput.keyboard import Controller
        self._keyboard = Controller()

    def type_char(self, char: str) -> None:
        from pynput.keyboard import Key
        if char == "\n":
            self._keyboard.tap(Key.enter)
        else:
            self._keyboard.type(char)

    def tap_enter(self) -> None:
        from pynput.keyboard import Key
        self._keyboard.tap(Key.enter)

    def press_special_key(self, key_spec: str) -> None:
        parts = [p.strip().lower() for p in key_spec.split('+')]

        def resolve(name: str):
            k = _SPECIAL_KEYS.get(name)
            if k is not None:
                return k
            if len(name) == 1:
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

    def start_esc_listener(self, on_esc: Callable[[], None]) -> Any:
        from pynput.keyboard import Key, Listener

        def on_key(key):
            if key == Key.esc:
                on_esc()
                return False

        listener = Listener(on_press=on_key)
        listener.start()
        return listener

    def wait_for_enter_or_esc(self, on_esc: Callable[[], None], stop_event: threading.Event) -> bool:
        from pynput.keyboard import Key, Listener

        proceed = threading.Event()
        result = [True]

        def on_key(key):
            if key == Key.enter:
                result[0] = True
                proceed.set()
                return False
            if key == Key.esc:
                result[0] = False
                on_esc()
                proceed.set()
                return False

        with Listener(on_press=on_key):
            while not proceed.is_set():
                if stop_event.is_set():
                    return False
                proceed.wait(timeout=0.05)

        return result[0]


# Scancode mapping tables for EvdevDriver
_EVDEV_ASCII_MAP: dict[str, tuple[int, bool]] = {}
_EVDEV_KEY_MAP: dict[str, int] = {}
_EVDEV_INITIALIZED = False


def _init_evdev_maps() -> None:
    global _EVDEV_INITIALIZED, _EVDEV_ASCII_MAP, _EVDEV_KEY_MAP
    if _EVDEV_INITIALIZED:
        return

    from evdev import ecodes as e

    _EVDEV_ASCII_MAP = {
        'a': (e.KEY_A, False), 'b': (e.KEY_B, False), 'c': (e.KEY_C, False), 'd': (e.KEY_D, False),
        'e': (e.KEY_E, False), 'f': (e.KEY_F, False), 'g': (e.KEY_G, False), 'h': (e.KEY_H, False),
        'i': (e.KEY_I, False), 'j': (e.KEY_J, False), 'k': (e.KEY_K, False), 'l': (e.KEY_L, False),
        'm': (e.KEY_M, False), 'n': (e.KEY_N, False), 'o': (e.KEY_O, False), 'p': (e.KEY_P, False),
        'q': (e.KEY_Q, False), 'r': (e.KEY_R, False), 's': (e.KEY_S, False), 't': (e.KEY_T, False),
        'u': (e.KEY_U, False), 'v': (e.KEY_V, False), 'w': (e.KEY_W, False), 'x': (e.KEY_X, False),
        'y': (e.KEY_Y, False), 'z': (e.KEY_Z, False),
        'A': (e.KEY_A, True),  'B': (e.KEY_B, True),  'C': (e.KEY_C, True),  'D': (e.KEY_D, True),
        'E': (e.KEY_E, True),  'F': (e.KEY_F, True),  'G': (e.KEY_G, True),  'H': (e.KEY_H, True),
        'I': (e.KEY_I, True),  'J': (e.KEY_J, True),  'K': (e.KEY_K, True),  'L': (e.KEY_L, True),
        'M': (e.KEY_M, True),  'N': (e.KEY_N, True),  'O': (e.KEY_O, True),  'P': (e.KEY_P, True),
        'Q': (e.KEY_Q, True),  'R': (e.KEY_R, True),  'S': (e.KEY_S, True),  'T': (e.KEY_T, True),
        'U': (e.KEY_U, True),  'V': (e.KEY_V, True),  'W': (e.KEY_W, True),  'X': (e.KEY_X, True),
        'Y': (e.KEY_Y, True),  'Z': (e.KEY_Z, True),
        '1': (e.KEY_1, False), '2': (e.KEY_2, False), '3': (e.KEY_3, False), '4': (e.KEY_4, False),
        '5': (e.KEY_5, False), '6': (e.KEY_6, False), '7': (e.KEY_7, False), '8': (e.KEY_8, False),
        '9': (e.KEY_9, False), '0': (e.KEY_0, False),
        ' ': (e.KEY_SPACE, False), '\t': (e.KEY_TAB, False), '\n': (e.KEY_ENTER, False),
        '-': (e.KEY_MINUS, False), '_': (e.KEY_MINUS, True),
        '=': (e.KEY_EQUAL, False), '+': (e.KEY_EQUAL, True),
        '[': (e.KEY_LEFTBRACE, False), '{': (e.KEY_LEFTBRACE, True),
        ']': (e.KEY_RIGHTBRACE, False), '}': (e.KEY_RIGHTBRACE, True),
        ';': (e.KEY_SEMICOLON, False), ':': (e.KEY_SEMICOLON, True),
        "'": (e.KEY_APOSTROPHE, False), '"': (e.KEY_APOSTROPHE, True),
        '`': (e.KEY_GRAVE, False), '~': (e.KEY_GRAVE, True),
        '\\': (e.KEY_BACKSLASH, False), '|': (e.KEY_BACKSLASH, True),
        ',': (e.KEY_COMMA, False), '<': (e.KEY_COMMA, True),
        '.': (e.KEY_DOT, False), '>': (e.KEY_DOT, True),
        '/': (e.KEY_SLASH, False), '?': (e.KEY_SLASH, True),
        '!': (e.KEY_1, True), '@': (e.KEY_2, True), '#': (e.KEY_3, True),
        '$': (e.KEY_4, True), '%': (e.KEY_5, True), '^': (e.KEY_6, True),
        '&': (e.KEY_7, True), '*': (e.KEY_8, True), '(': (e.KEY_9, True),
        ')': (e.KEY_0, True),
    }

    _EVDEV_KEY_MAP = {
        'f1': e.KEY_F1, 'f2': e.KEY_F2, 'f3': e.KEY_F3, 'f4': e.KEY_F4,
        'f5': e.KEY_F5, 'f6': e.KEY_F6, 'f7': e.KEY_F7, 'f8': e.KEY_F8,
        'f9': e.KEY_F9, 'f10': e.KEY_F10, 'f11': e.KEY_F11, 'f12': e.KEY_F12,
        'ctrl': e.KEY_LEFTCTRL, 'control': e.KEY_LEFTCTRL,
        'alt': e.KEY_LEFTALT, 'altgr': e.KEY_RIGHTALT,
        'shift': e.KEY_LEFTSHIFT,
        'win': e.KEY_LEFTMETA, 'super': e.KEY_LEFTMETA, 'cmd': e.KEY_LEFTMETA,
        'esc': e.KEY_ESC, 'escape': e.KEY_ESC,
        'tab': e.KEY_TAB,
        'enter': e.KEY_ENTER, 'return': e.KEY_ENTER,
        'backspace': e.KEY_BACKSPACE,
        'delete': e.KEY_DELETE, 'del': e.KEY_DELETE,
        'insert': e.KEY_INSERT, 'ins': e.KEY_INSERT,
        'home': e.KEY_HOME, 'end': e.KEY_END,
        'pageup': e.KEY_PAGEUP, 'pgup': e.KEY_PAGEUP,
        'pagedown': e.KEY_PAGEDOWN, 'pgdn': e.KEY_PAGEDOWN,
        'up': e.KEY_UP, 'down': e.KEY_DOWN, 'left': e.KEY_LEFT, 'right': e.KEY_RIGHT,
        'space': e.KEY_SPACE,
        'capslock': e.KEY_CAPSLOCK,
        'numlock': e.KEY_NUMLOCK,
        'scrolllock': e.KEY_SCROLLLOCK,
        'printscreen': e.KEY_SYSRQ,
        'pause_break': e.KEY_PAUSE,
    }

    _EVDEV_INITIALIZED = True


def _find_physical_keyboards(virtual_name: str) -> list[Any]:
    """Find all physical keyboard InputDevice nodes, excluding virtual devices."""
    import evdev
    from evdev import ecodes as e

    keyboards = []
    for path in evdev.list_devices():
        try:
            dev = evdev.InputDevice(path)
            if dev.name == virtual_name:
                dev.close()
                continue
            caps = dev.capabilities()
            if e.EV_KEY in caps:
                keys = caps[e.EV_KEY]
                if e.KEY_ESC in keys and e.KEY_ENTER in keys:
                    keyboards.append(dev)
                    continue
            dev.close()
        except (OSError, PermissionError):
            continue
    return keyboards


class EvdevEscListener:
    """Monitors physical keyboards for the ESC key to signal early abort."""

    def __init__(self, on_esc: Callable[[], None], virtual_name: str = "AutoTyper-Virtual-Keyboard") -> None:
        self._on_esc = on_esc
        self._virtual_name = virtual_name
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        from evdev import ecodes as e

        keyboards = _find_physical_keyboards(self._virtual_name)
        if not keyboards:
            return
        fd_map = {kb.fd: kb for kb in keyboards}
        try:
            while not self._stop_event.is_set():
                r, _, _ = select.select(list(fd_map.keys()), [], [], 0.05)
                for fd in r:
                    kb = fd_map.get(fd)
                    if not kb:
                        continue
                    try:
                        for event in kb.read():
                            if event.type == e.EV_KEY and event.code == e.KEY_ESC and event.value == 1:
                                self._on_esc()
                                return
                    except (OSError, BlockingIOError):
                        pass
        finally:
            for kb in keyboards:
                try:
                    kb.close()
                except Exception:
                    pass


class EvdevDriver(BaseKeyboardDriver):
    """Keyboard driver using Linux /dev/uinput and /dev/input (Wayland & Linux native)."""

    VIRTUAL_NAME = "AutoTyper-Virtual-Keyboard"

    def __init__(self) -> None:
        _init_evdev_maps()
        from evdev import UInput, ecodes as e

        supported_keys = set(code for code, _ in _EVDEV_ASCII_MAP.values()) | set(_EVDEV_KEY_MAP.values()) | {
            e.KEY_LEFTSHIFT, e.KEY_RIGHTSHIFT, e.KEY_LEFTCTRL, e.KEY_RIGHTCTRL,
            e.KEY_LEFTALT, e.KEY_RIGHTALT, e.KEY_LEFTMETA
        }
        self._ui = UInput({e.EV_KEY: list(supported_keys)}, name=self.VIRTUAL_NAME)
        # Give compositor a moment to register the new virtual device
        time.sleep(0.05)

    def type_char(self, char: str) -> None:
        from evdev import ecodes as e

        mapping = _EVDEV_ASCII_MAP.get(char)
        if not mapping:
            return
        code, shift = mapping
        if shift:
            self._ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
        self._ui.write(e.EV_KEY, code, 1)
        self._ui.syn()
        time.sleep(0.002)
        self._ui.write(e.EV_KEY, code, 0)
        if shift:
            self._ui.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
        self._ui.syn()

    def tap_enter(self) -> None:
        from evdev import ecodes as e
        self._ui.write(e.EV_KEY, e.KEY_ENTER, 1)
        self._ui.syn()
        time.sleep(0.002)
        self._ui.write(e.EV_KEY, e.KEY_ENTER, 0)
        self._ui.syn()

    def press_special_key(self, key_spec: str) -> None:
        from evdev import ecodes as e

        parts = [p.strip().lower() for p in key_spec.split('+')]

        def resolve(name: str) -> int | None:
            k = _EVDEV_KEY_MAP.get(name)
            if k is not None:
                return k
            if len(name) == 1:
                m = _EVDEV_ASCII_MAP.get(name)
                if m:
                    return m[0]
            return None

        keys = [k for k in (resolve(p) for p in parts) if k is not None]
        if not keys:
            return
        if len(keys) == 1:
            self._ui.write(e.EV_KEY, keys[0], 1)
            self._ui.syn()
            time.sleep(0.005)
            self._ui.write(e.EV_KEY, keys[0], 0)
            self._ui.syn()
        else:
            held: list[int] = []
            try:
                for k in keys[:-1]:
                    self._ui.write(e.EV_KEY, k, 1)
                    held.append(k)
                self._ui.write(e.EV_KEY, keys[-1], 1)
                self._ui.syn()
                time.sleep(0.005)
                self._ui.write(e.EV_KEY, keys[-1], 0)
                self._ui.syn()
            finally:
                for k in reversed(held):
                    self._ui.write(e.EV_KEY, k, 0)
                self._ui.syn()

    def start_esc_listener(self, on_esc: Callable[[], None]) -> Any:
        listener = EvdevEscListener(on_esc, virtual_name=self.VIRTUAL_NAME)
        listener.start()
        return listener

    def wait_for_enter_or_esc(self, on_esc: Callable[[], None], stop_event: threading.Event) -> bool:
        from evdev import ecodes as e

        keyboards = _find_physical_keyboards(self.VIRTUAL_NAME)
        if not keyboards:
            while not stop_event.is_set():
                time.sleep(0.05)
            return False

        fd_map = {kb.fd: kb for kb in keyboards}
        try:
            while not stop_event.is_set():
                r, _, _ = select.select(list(fd_map.keys()), [], [], 0.05)
                for fd in r:
                    kb = fd_map.get(fd)
                    if not kb:
                        continue
                    try:
                        for event in kb.read():
                            if event.type == e.EV_KEY and event.value == 1:
                                if event.code == e.KEY_ENTER:
                                    return True
                                if event.code == e.KEY_ESC:
                                    on_esc()
                                    return False
                    except (OSError, BlockingIOError):
                        pass
            return False
        finally:
            for kb in keyboards:
                try:
                    kb.close()
                except Exception:
                    pass

    def close(self) -> None:
        try:
            self._ui.close()
        except Exception:
            pass


def is_wayland() -> bool:
    """Return True if running under a Linux Wayland session."""
    return sys.platform == "linux" and (
        os.environ.get("XDG_SESSION_TYPE") == "wayland" or
        bool(os.environ.get("WAYLAND_DISPLAY"))
    )


def can_use_evdev() -> bool:
    """Return True if evdev is installed and /dev/uinput is writable."""
    if sys.platform != "linux":
        return False
    try:
        import evdev  # noqa: F401
        return os.access("/dev/uinput", os.W_OK)
    except Exception:
        return False


def get_keyboard_driver() -> tuple[BaseKeyboardDriver, str]:
    """
    Instantiate and return (driver_instance, driver_name).
    driver_name is 'evdev' or 'pynput'.
    Falls back gracefully to PynputDriver if EvdevDriver cannot be created.
    """
    if is_wayland() and can_use_evdev():
        try:
            return EvdevDriver(), "evdev"
        except Exception:
            pass
    return PynputDriver(), "pynput"
