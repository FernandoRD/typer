"""CLI entry point: parse_args() and run_headless()."""

import argparse
import sys
import threading

from .engine import TypingEngine, TypingCallbacks
from .markers import parse_instructions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="typer",
        description="AutoTyper — simulates keyboard typing of any text.")
    parser.add_argument("--file",     "-f", metavar="FILE",
                        help="Text file to load on startup.")
    parser.add_argument("--interval", "-i", type=float, default=100.0, metavar="MS",
                        help="Typing interval in milliseconds (default: 100).")
    parser.add_argument("--wait",     "-w", type=float, default=2.0,   metavar="S",
                        help="Seconds to wait before typing (default: 2).")
    parser.add_argument("--lang",     "-l", choices=["en", "pt"], default="en",
                        help="Interface language: en or pt (default: en).")
    parser.add_argument("--headless", action="store_true",
                        help="Run without GUI. Requires --file.")
    return parser.parse_args()


def run_headless(file_path: str, interval_ms: float, wait_s: float) -> None:
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    instructions = parse_instructions(text)
    total_chars  = sum(1 for op, _ in instructions if op == 'char')

    print(f"AutoTyper headless | {total_chars} chars | {interval_ms} ms interval")
    print(f"Waiting {wait_s}s — switch to the target window now…")
    print("Typing… (press Ctrl+C or ESC to stop)")

    done_event = threading.Event()
    result     = {"done": 0, "total": total_chars, "stopped": False}

    def on_done(stopped: bool, done: int, total: int) -> None:
        result["stopped"] = stopped
        result["done"]    = done
        result["total"]   = total
        done_event.set()

    callbacks = TypingCallbacks(on_done=on_done)
    engine = TypingEngine()

    try:
        engine.start(text, wait_s, interval_ms / 1000.0, False, callbacks)
        done_event.wait()
    except KeyboardInterrupt:
        engine.stop()
        done_event.wait(timeout=2.0)

    print(f"\nDone. {result['done']}/{result['total']} characters typed.")
