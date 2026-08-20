import argparse
import re
from pathlib import Path
from typing import Optional, List

from kingstack.archive import create_archive, verify_archive
from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths


_ARCHIVE_ID = re.compile(r"^archive-[0-9]{8}-[0-9]{6}$")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kingstack")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--home", type=Path, default=Path.home())
    inventory.add_argument("--output", type=Path, required=True)
    archive = commands.add_parser("archive")
    archive_commands = archive.add_subparsers(dest="archive_action", required=True)
    create = archive_commands.add_parser("create")
    create.add_argument("--home", type=Path, default=Path.home())
    create.add_argument("--label", required=True)
    create.add_argument("--print-id", action="store_true")
    verify = archive_commands.add_parser("verify")
    verify.add_argument("identifier")
    verify.add_argument("--home", type=Path, default=Path.home())
    verify.add_argument("--check-permissions", action="store_true")
    arguments = parser.parse_args(argv)

    if arguments.command == "inventory":
        write_public_report(
            capture_baseline(Paths.for_home(arguments.home)), arguments.output
        )
        return 0
    if arguments.command == "archive":
        try:
            if arguments.archive_action == "create":
                paths = Paths.for_home(arguments.home)
                created = create_archive(paths, paths.runtime / "archives", arguments.label)
                if arguments.print_id:
                    print(created.name)
                else:
                    print(created)
                return 0
            if arguments.archive_action == "verify":
                if not _ARCHIVE_ID.fullmatch(arguments.identifier):
                    parser.error("invalid archive identifier")
                archive_dir = Paths.for_home(arguments.home).runtime / "archives" / arguments.identifier
                problems = verify_archive(archive_dir, arguments.check_permissions)
                if problems:
                    for problem in problems:
                        print(problem)
                    return 1
                print("verified " + arguments.identifier)
                return 0
        except ValueError as error:
            parser.error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
