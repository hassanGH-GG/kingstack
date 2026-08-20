import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional, List

from kingstack.adapter_contract import (
    ADAPTER_ID_PATTERN,
    AdapterContractError,
    load_adapter,
    load_capability_catalog,
    validate_adapter,
)
from kingstack.bootstrap import BootstrapError, bootstrap
from kingstack.inventory import capture_baseline, write_public_report
from kingstack.paths import Paths
from kingstack.render import RenderError, render_bundle


def _adapter_id(value: str) -> str:
    if ADAPTER_ID_PATTERN.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(
            "adapter must be a stable ID containing lowercase letters, digits, '_' or '-'"
        )
    return value


def _load_selected_adapter(
    root: Path, adapter: Optional[str], adapter_path: Optional[Path]
):
    if adapter is not None:
        declaration = load_adapter(root / "adapters" / adapter / "adapter.json")
        if declaration.id != adapter:
            raise AdapterContractError(
                "adapter selector '{}' loaded declaration id '{}'".format(
                    adapter, declaration.id
                )
            )
        return declaration
    path = adapter_path
    if path is not None and not path.is_absolute():
        path = root / path
    return load_adapter(path)


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
    check_command = commands.add_parser("check")
    check_command.add_argument("--contract", action="store_true")
    adapter_selector = check_command.add_mutually_exclusive_group(required=True)
    adapter_selector.add_argument("--adapter", type=_adapter_id)
    adapter_selector.add_argument("--adapter-path", type=Path)
    render_command = commands.add_parser("render")
    render_command.add_argument("--adapter", type=_adapter_id, required=True)
    render_selector = render_command.add_mutually_exclusive_group(required=True)
    render_selector.add_argument("--manifest", action="store_true")
    render_selector.add_argument("--print-file")
    render_selector.add_argument("--check-file")
    render_command.add_argument("--equals", type=Path)
    arguments = parser.parse_args(argv)

    if arguments.command == "render":
        if arguments.check_file is not None and arguments.equals is None:
            render_command.error("--check-file requires --equals FILE")
        if arguments.check_file is None and arguments.equals is not None:
            render_command.error("--equals is valid only with --check-file")

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
    if arguments.command == "check":
        if not arguments.contract:
            check_command.error("--contract is required")
        root = Path(__file__).resolve().parents[2]
        try:
            declaration = _load_selected_adapter(
                root, arguments.adapter, arguments.adapter_path
            )
            catalog = load_capability_catalog(root / "core/capabilities/catalog.json")
            errors = validate_adapter(declaration, catalog)
        except AdapterContractError as error:
            print("kingstack check: {}".format(error), file=sys.stderr)
            return 2
        if errors:
            for error in errors:
                print("kingstack check: {}".format(error), file=sys.stderr)
            return 2
        print("{} adapter contract valid".format(declaration.id))
        return 0
    if arguments.command == "render":
        root = Path(__file__).resolve().parents[2]
        try:
            bundle = render_bundle(arguments.adapter, root)
            selected_path = arguments.print_file or arguments.check_file
            if selected_path is not None and selected_path not in bundle:
                raise RenderError(
                    "rendered bundle has no canonical path '{}'".format(selected_path)
                )
            if arguments.manifest:
                document = {
                    "schema_version": 1,
                    "adapter": arguments.adapter,
                    "files": [
                        {
                            "path": path,
                            "size": len(content),
                            "sha256": hashlib.sha256(content).hexdigest(),
                        }
                        for path, content in bundle.items()
                    ],
                }
                print(json.dumps(document, indent=2, sort_keys=True))
                return 0
            if arguments.print_file is not None:
                sys.stdout.buffer.write(bundle[arguments.print_file])
                return 0
            try:
                expected = arguments.equals.read_bytes()
            except OSError as error:
                raise RenderError(
                    "cannot read comparison file '{}': {}".format(arguments.equals, error)
                ) from error
            return 0 if bundle[arguments.check_file] == expected else 1
        except (RenderError, AdapterContractError) as error:
            print("kingstack render: {}".format(error), file=sys.stderr)
            return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
