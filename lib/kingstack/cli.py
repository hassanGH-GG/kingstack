import argparse
import json
import sys
from pathlib import Path
from typing import Optional, List

from kingstack.bootstrap import BootstrapError, bootstrap
from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kingstack")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--home", type=Path, default=Path.home())
    inventory.add_argument("--output", type=Path, required=True)
    bootstrap_command = commands.add_parser("bootstrap")
    bootstrap_command.add_argument("--source-repo", type=Path, required=True)
    bootstrap_command.add_argument(
        "--destination", type=Path, default=Paths.for_home(Path.home()).repo,
    )
    bootstrap_command.add_argument(
        "--runtime", type=Path, default=Paths.for_home(Path.home()).runtime,
    )
    bootstrap_command.add_argument(
        "--baseline-home", action="append", type=Path, required=True,
    )
    bootstrap_command.add_argument("--allow-unpushed", action="store_true")
    bootstrap_command.add_argument("--dry-run", action="store_true")
    arguments = parser.parse_args(argv)

    if arguments.command == "inventory":
        write_public_report(
            capture_baseline(Paths.for_home(arguments.home)), arguments.output
        )
        return 0
    if arguments.command == "bootstrap":
        try:
            result = bootstrap(
                source_repo=arguments.source_repo,
                destination=arguments.destination,
                runtime=arguments.runtime,
                baseline_homes=arguments.baseline_home,
                allow_unpushed=arguments.allow_unpushed,
                dry_run=arguments.dry_run,
            )
        except BootstrapError as error:
            print("kingstack bootstrap: " + str(error), file=sys.stderr)
            return 2
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
