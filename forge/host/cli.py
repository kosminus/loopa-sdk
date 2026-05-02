from __future__ import annotations

import sys
from pathlib import Path

from .config import load_spec
from .supervisor import Supervisor


USAGE = "usage: forge run <app_dir>"


def main(argv: list[str] | None = None) -> int:
    args = list(argv if argv is not None else sys.argv[1:])

    if not args or args[0] in {"-h", "--help"}:
        print(USAGE)
        return 0 if args else 2

    if args[0] != "run":
        print(f"unknown command: {args[0]}", file=sys.stderr)
        print(USAGE, file=sys.stderr)
        return 2

    if len(args) < 2:
        print(USAGE, file=sys.stderr)
        return 2

    spec = load_spec(Path(args[1]))
    return Supervisor(spec).run()


if __name__ == "__main__":
    raise SystemExit(main())
