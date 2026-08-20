import argparse
from pathlib import Path
from typing import Optional, List

from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kingstack")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--home", type=Path, default=Path.home())
    inventory.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args(argv)

    if arguments.command == "inventory":
        write_public_report(
            capture_baseline(Paths.for_home(arguments.home)), arguments.output
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
