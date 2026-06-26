"""Marker parsing: _MARKER_RE, _SPECIAL_KEYS, Instruction, parse_instructions()."""

import re
from typing import TypeAlias

from pynput.keyboard import Key

# Matches [[directive:value]] markers embedded in text
_MARKER_RE = re.compile(r'\[\[(\w+):([^\]]*)\]\]', re.IGNORECASE)

# Public type alias for one entry in the instruction list
Instruction: TypeAlias = tuple[str, str | float | None]

# Maps [[key:name]] values to pynput Key constants (case-insensitive lookup)
_SPECIAL_KEYS: dict[str, Key] = {
    # Function keys
    'f1': Key.f1,  'f2': Key.f2,  'f3': Key.f3,  'f4': Key.f4,
    'f5': Key.f5,  'f6': Key.f6,  'f7': Key.f7,  'f8': Key.f8,
    'f9': Key.f9,  'f10': Key.f10, 'f11': Key.f11, 'f12': Key.f12,
    # Modifiers
    'ctrl': Key.ctrl, 'alt': Key.alt, 'altgr': Key.alt_gr,
    'shift': Key.shift, 'win': Key.cmd,
    # Navigation / editing
    'esc': Key.esc, 'tab': Key.tab, 'enter': Key.enter,
    'backspace': Key.backspace, 'delete': Key.delete,
    'home': Key.home, 'end': Key.end,
    'pageup': Key.page_up, 'pagedown': Key.page_down,
    'up': Key.up, 'down': Key.down, 'left': Key.left, 'right': Key.right,
    'insert': Key.insert, 'space': Key.space,
    # Lock / system
    'capslock': Key.caps_lock, 'numlock': Key.num_lock,
    'scrolllock': Key.scroll_lock, 'printscreen': Key.print_screen,
    'pause_break': Key.pause,
}


def parse_instructions(text: str) -> list[Instruction]:
    """
    Convert raw text into a flat instruction list:
      ('char',  str)   — type this character
      ('pause', float) — sleep N seconds (N must be > 0)
      ('speed', float) — change interval to N ms (N must be > 0)
      ('speed', None)  — reset interval to the base value
      ('key',   str)   — press a special key or chord
    Markers that are malformed, use unknown directives, or specify non-positive
    numeric values are silently dropped.
    """
    instructions: list[Instruction] = []
    pos = 0
    for m in _MARKER_RE.finditer(text):
        for ch in text[pos:m.start()]:
            instructions.append(('char', ch))
        cmd, val = m.group(1).lower(), m.group(2).strip()
        if cmd == 'pause':
            try:
                secs = float(val)
                if secs > 0:
                    instructions.append(('pause', secs))
            except ValueError:
                pass
        elif cmd == 'speed':
            if val.lower() == 'reset':
                instructions.append(('speed', None))
            else:
                try:
                    ms = float(val)
                    if ms > 0:
                        instructions.append(('speed', ms))
                except ValueError:
                    pass
        elif cmd == 'key' and val:
            instructions.append(('key', val))
        pos = m.end()
    for ch in text[pos:]:
        instructions.append(('char', ch))
    return instructions
