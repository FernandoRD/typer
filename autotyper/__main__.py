"""Entry point for `python -m autotyper`."""

import sys

from .cli import parse_args, run_headless
from .app import TyperApp


def main() -> None:
    args = parse_args()

    if args.headless:
        if not args.file:
            print("Error: --headless requires --file.")
            sys.exit(1)
        run_headless(args.file, args.interval, args.wait)
    else:
        app = TyperApp(
            lang=args.lang,
            initial_file=args.file,
            interval_ms=int(args.interval),
            wait_s=args.wait,
        )
        app.mainloop()


if __name__ == "__main__":
    main()
