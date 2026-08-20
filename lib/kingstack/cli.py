import argparse
from pathlib import Path
from typing import Optional, List

from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths
from kingstack.snapshot import (
    create_snapshot,
    current_destination_hash,
    restore_snapshot,
    snapshot_path,
    verify_snapshot,
)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(prog="kingstack")
    commands = parser.add_subparsers(dest="command", required=True)
    inventory = commands.add_parser("inventory")
    inventory.add_argument("--home", type=Path, default=Path.home())
    inventory.add_argument("--output", type=Path, required=True)
    snapshot = commands.add_parser("snapshot")
    snapshot.set_defaults(snapshot_action="create")
    snapshot.add_argument("--home", type=Path, default=Path.home())
    snapshot.add_argument("--label", default="manual-snapshot")
    snapshot.add_argument("--print-id", action="store_true")
    snapshot_commands = snapshot.add_subparsers(dest="snapshot_action")
    verify = snapshot_commands.add_parser("verify")
    verify.add_argument("identifier")
    verify.add_argument("--home", type=Path, default=Path.home())
    verify.add_argument("--check-permissions", action="store_true")
    restore = snapshot_commands.add_parser("restore")
    restore.add_argument("identifier")
    restore.add_argument("--home", type=Path, default=Path.home())
    restore.add_argument("--destination-home", type=Path, default=Path.home())
    restore.add_argument("--apply", action="store_true")
    restore.add_argument("--expected-current-hash")
    arguments = parser.parse_args(argv)

    if arguments.command == "inventory":
        write_public_report(
            capture_baseline(Paths.for_home(arguments.home)), arguments.output
        )
        return 0
    if arguments.command == "snapshot":
        try:
            if arguments.snapshot_action in (None, "create"):
                paths = Paths.for_home(arguments.home)
                created = create_snapshot(paths, paths.runtime / "snapshots", arguments.label)
                if arguments.print_id:
                    print(created.name)
                else:
                    print(created)
                return 0
            if arguments.snapshot_action == "verify":
                snapshot_dir = snapshot_path(Paths.for_home(arguments.home).runtime / "snapshots", arguments.identifier)
                problems = verify_snapshot(snapshot_dir, arguments.check_permissions)
                if problems:
                    for problem in problems:
                        print(problem)
                    return 1
                print("verified " + arguments.identifier)
                return 0
            if arguments.snapshot_action == "restore":
                if arguments.apply and not arguments.expected_current_hash:
                    parser.error("--apply requires --expected-current-hash")
                snapshot_dir = snapshot_path(Paths.for_home(arguments.home).runtime / "snapshots", arguments.identifier)
                planned = restore_snapshot(
                    snapshot_dir,
                    arguments.destination_home,
                    dry_run=not arguments.apply,
                    expected_current_hash=arguments.expected_current_hash,
                )
                for path in planned:
                    print(path)
                if not arguments.apply:
                    print("expected-current-hash=" + current_destination_hash(snapshot_dir, arguments.destination_home))
                return 0
        except ValueError as error:
            parser.error(str(error))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
