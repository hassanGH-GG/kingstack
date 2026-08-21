import argparse
from collections.abc import Mapping
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
from kingstack.parity import rendered_parity
from kingstack.render import RenderError, render_bundle
from kingstack.skills import (
    SkillCatalogError,
    bundle_manifest,
    check_clobber_manifest,
    check_upstream,
    semantic_parity_errors,
)


def _plain(value):
    if isinstance(value, Mapping):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_plain(item) for item in value]
    return value


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
    inventory = commands.add_parser("inventory", help="write a redacted home inventory")
    inventory.add_argument("--home", type=Path, default=Path.home())
    inventory.add_argument("--output", type=Path, required=True)
    bootstrap_command = commands.add_parser("bootstrap", help="clone kingstack into a new checkout")
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
    setup_command = commands.add_parser(
        "setup",
        help="prepare a private runtime; never writes a native home",
        epilog="Examples:\n  kingstack setup\n  kingstack setup --identity personal --json\n  kingstack setup --root ~/src/kingstack --runtime ~/.kingstack",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    setup_command.add_argument("--root", type=Path, help="kingstack checkout")
    setup_command.add_argument("--runtime", type=Path, help="private runtime, default ~/.kingstack")
    setup_command.add_argument("--identity", choices=("personal", "hassan"), default="personal")
    setup_command.add_argument("--headroom", type=Path, help="headroom checkout")
    setup_command.add_argument("--home", type=Path, default=Path.home())
    setup_command.add_argument("--json", action="store_true")
    check_command = commands.add_parser("check", help="run staged or live health")
    check_mode = check_command.add_mutually_exclusive_group(required=True)
    check_mode.add_argument("--contract", action="store_true")
    check_mode.add_argument("--rendered", action="store_true")
    check_mode.add_argument("--core", action="store_true")
    check_mode.add_argument("--memory", action="store_true")
    check_mode.add_argument("--schedules", action="store_true")
    check_mode.add_argument("--all", dest="check_all", action="store_true")
    adapter_selector = check_command.add_mutually_exclusive_group(required=False)
    adapter_selector.add_argument("--adapter", type=_adapter_id)
    adapter_selector.add_argument("--adapter-path", type=Path)
    check_command.add_argument("--mode", choices=("staged", "live"))
    check_command.add_argument("--json", action="store_true")
    render_command = commands.add_parser("render", help="print an immutable adapter bundle")
    render_command.add_argument("--adapter", type=_adapter_id, required=True)
    render_selector = render_command.add_mutually_exclusive_group(required=True)
    render_selector.add_argument("--manifest", action="store_true")
    render_selector.add_argument("--print-file")
    render_selector.add_argument("--check-file")
    render_command.add_argument("--equals", type=Path)
    sync_command = commands.add_parser("sync-upstream", help="check or manifest a pinned upstream")
    sync_command.add_argument("upstream", choices=("pstack", "headroom"))
    sync_mode = sync_command.add_mutually_exclusive_group(required=True)
    sync_mode.add_argument("--bundle-manifest", action="store_true")
    sync_mode.add_argument("--check", action="store_true")
    sync_command.add_argument("--adapter", type=_adapter_id)
    sync_command.add_argument("--upstream-root", type=Path)
    sync_command.add_argument("--installed-root", type=Path)
    sync_command.add_argument("--installed-manifest", type=Path)
    memory_command = commands.add_parser("memory", help="review the private shared memory store")
    memory_action = memory_command.add_subparsers(dest="memory_command", required=True)
    memory_list = memory_action.add_parser("list")
    memory_list.add_argument("--project")
    memory_list.add_argument("--root", type=Path)
    memory_show = memory_action.add_parser("show")
    memory_show.add_argument("candidate_id")
    memory_show.add_argument("--root", type=Path)
    memory_migrate = memory_action.add_parser("migrate-claude")
    memory_migrate.add_argument("--dry-run", action="store_true")
    memory_migrate.add_argument("--apply", action="store_true")
    memory_migrate.add_argument("--claude-home", type=Path)
    memory_migrate.add_argument("--root", type=Path)
    memory_promote = memory_action.add_parser("promote")
    memory_promote.add_argument("candidate_id")
    memory_promote.add_argument("--name", required=True)
    memory_promote.add_argument("--type", dest="memory_type", required=True)
    memory_promote.add_argument("--description", required=True)
    memory_promote.add_argument("--body", required=True)
    memory_promote.add_argument("--actor", default="hassan")
    memory_promote.add_argument("--root", type=Path)
    memory_reject = memory_action.add_parser("reject")
    memory_reject.add_argument("candidate_id")
    memory_reject.add_argument("--reason", required=True)
    memory_reject.add_argument("--actor", default="hassan")
    memory_reject.add_argument("--root", type=Path)
    memory_recall = memory_action.add_parser("recall")
    memory_recall.add_argument("names", nargs="+")
    memory_recall.add_argument("--cwd", type=Path)
    memory_recall.add_argument("--root", type=Path)
    memory_consolidate = memory_action.add_parser("consolidate")
    memory_consolidate.add_argument("--root", type=Path)
    memory_harvest = memory_action.add_parser("harvest")
    memory_harvest.add_argument("--inbox", type=Path, required=True)
    memory_harvest.add_argument("--cwd", type=Path)
    memory_harvest.add_argument("--adapter", default="claude")
    memory_harvest.add_argument("--root", type=Path)
    handoff_command = commands.add_parser("handoff", help="write a packet for another adapter")
    handoff_command.add_argument("--finish", required=True)
    handoff_command.add_argument("--out", type=Path)
    handoff_command.add_argument("--cwd", type=Path)
    handoff_command.add_argument("--store", type=Path)
    handoff_command.add_argument("--memory-root", type=Path)
    handoff_command.add_argument("--session")
    handoff_command.add_argument("--sessions-root", type=Path)
    session_command = commands.add_parser(
        "session",
        help="list or continue the private working-set index",
        epilog="Examples:\n  kingstack session list\n  kingstack session show s_abc123\n  kingstack session continue s_abc123 --finish \"<done means>\"",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    session_action = session_command.add_subparsers(dest="session_command", required=True)
    session_list = session_action.add_parser("list")
    session_list.add_argument("--project")
    session_list.add_argument("--cwd", type=Path)
    session_list.add_argument("--root", type=Path)
    session_show = session_action.add_parser("show")
    session_show.add_argument("session_id")
    session_show.add_argument("--root", type=Path)
    session_continue = session_action.add_parser("continue")
    session_continue.add_argument("session_id")
    session_continue.add_argument("--finish")
    session_continue.add_argument("--out", type=Path)
    session_continue.add_argument("--cwd", type=Path)
    session_continue.add_argument("--root", type=Path)
    session_continue.add_argument("--store", type=Path)
    session_continue.add_argument("--memory-root", type=Path)
    release_command = commands.add_parser("release", help="build or select a private release")
    release_command.add_argument("--adapter", type=_adapter_id, required=True)
    release_command.add_argument("--runtime", type=Path, required=True)
    release_mode = release_command.add_mutually_exclusive_group(required=True)
    release_mode.add_argument("--build", action="store_true")
    release_mode.add_argument("--list", action="store_true")
    release_mode.add_argument("--select", action="store_true")
    release_mode.add_argument("--rollback", action="store_true")
    release_command.add_argument("--to")
    effort_command = commands.add_parser(
        "effort",
        help="scan spawn lines; inherit is fail",
        epilog="Examples:\n  kingstack effort --file transcript.jsonl\n  kingstack effort < transcript.txt",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    effort_command.add_argument("--file", type=Path)
    status_command = commands.add_parser("status", help="print model, effort, context, and subagent models")
    status_command.add_argument("--transcript", dest="transcript_path")
    status_command.add_argument("--model", dest="status_model")
    status_command.add_argument("--effort", dest="status_effort")
    activate_command = commands.add_parser("activate", help="plan or apply a native-home link")
    activate_command.add_argument("--adapter", type=_adapter_id, required=True)
    activate_command.add_argument("--release", required=True)
    activate_command.add_argument("--runtime", type=Path, required=True)
    activate_command.add_argument("--native-home", type=Path, required=True)
    activate_command.add_argument("--dry-run", action="store_true")
    activate_command.add_argument("--apply", action="store_true")
    activate_command.add_argument("--approved-briefing", type=Path)
    headroom_command = commands.add_parser("headroom", help="archive and retrieve large tool output")
    headroom_action = headroom_command.add_subparsers(dest="headroom_command", required=True)
    crush_command = headroom_action.add_parser("crush")
    crush_command.add_argument("--file", type=Path)
    crush_command.add_argument("--store", type=Path)
    crush_command.add_argument("--tool", default="tool")
    retrieve_command = headroom_action.add_parser("retrieve")
    retrieve_command.add_argument("archive_id")
    retrieve_command.add_argument("--store", type=Path)
    stats_command = headroom_action.add_parser("stats")
    stats_command.add_argument("--store", type=Path)
    arguments = parser.parse_args(argv)

    if arguments.command == "render":
        if arguments.check_file is not None and arguments.equals is None:
            render_command.error("--check-file requires --equals FILE")
        if arguments.check_file is None and arguments.equals is not None:
            render_command.error("--equals is valid only with --check-file")
    if arguments.command == "sync-upstream":
        if arguments.bundle_manifest and arguments.adapter is None:
            sync_command.error("--bundle-manifest requires --adapter")
        if (arguments.installed_root is None) != (arguments.installed_manifest is None):
            sync_command.error("--installed-root and --installed-manifest are required together")
        if arguments.installed_root is not None and arguments.adapter is None:
            sync_command.error("installed clobber checking requires --adapter")
    if arguments.command == "release" and (arguments.select or arguments.rollback) and not arguments.to:
        release_command.error("--select and --rollback require --to")
    if arguments.command == "check":
        if (arguments.contract or arguments.rendered) and arguments.adapter is None and arguments.adapter_path is None:
            check_command.error("--contract and --rendered require --adapter or --adapter-path")
        if arguments.check_all and arguments.mode is None:
            check_command.error("--all requires --mode staged or --mode live")
    if arguments.command == "activate":
        if arguments.dry_run == arguments.apply:
            activate_command.error("pass exactly one of --dry-run or --apply")
        if arguments.apply:
            briefing = arguments.approved_briefing
            if briefing is None or briefing.name != "pre-link-briefing.md" or not briefing.is_file():
                activate_command.error("--apply requires --approved-briefing pre-link-briefing.md")

    if arguments.command == "effort":
        from kingstack.effort import failed, scan_file, scan_stream
        try:
            rows = scan_file(arguments.file) if arguments.file is not None else scan_stream(sys.stdin)
        except OSError as error:
            print("kingstack effort: {}".format(error), file=sys.stderr)
            return 2
        print(json.dumps(_plain({"schema_version": 1, "rows": rows, "failed": failed(rows)}), indent=2, sort_keys=True))
        return 1 if failed(rows) else 0
    if arguments.command == "status":
        from kingstack.statusline import render_status
        payload = {
            "transcript_path": arguments.transcript_path or "",
            "workspace": {"current_dir": str(Path.cwd())},
            "model": {"display_name": arguments.status_model or ""},
            "effort": {"level": arguments.status_effort or ""},
            "cost": {},
        }
        print(render_status(payload))
        return 0
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
    if arguments.command == "setup":
        from kingstack.setup import SetupError, setup
        try:
            report = setup(
                checkout=arguments.root,
                runtime=arguments.runtime,
                identity=arguments.identity,
                home=arguments.home,
                headroom_checkout=arguments.headroom,
            )
        except SetupError as error:
            print("kingstack setup: {}".format(error), file=sys.stderr)
            return 2
        if arguments.json:
            print(json.dumps(_plain(report), indent=2, sort_keys=True))
        else:
            print("checkout: {}".format(report["checkout"]))
            print("runtime: {}".format(report["runtime"]))
            print("identity: {}".format(report["identity"]))
            print("pstack: {status} {revision}".format(**report["pstack"]))
            if report["pstack"].get("clone"):
                print("clone: {}".format(report["pstack"]["clone"]))
            print("headroom: {status} {revision}".format(**report["headroom"]))
            if report["headroom"]["clone"]:
                print("clone: {}".format(report["headroom"]["clone"]))
            print("staged: {}".format(report["staged"]))
            if report["failing"]:
                print("failing: {}".format(", ".join(report["failing"])))
            print("got: {}".format(", ".join(report["got"])))
            print("not_got: {}".format(", ".join(report["not_got"])))
            print("native homes: not written")
        return 0 if report["staged"] == "healthy" else 1
    if arguments.command == "check":
        root = Path(__file__).resolve().parents[2]
        if arguments.rendered:
            if arguments.adapter is None:
                check_command.error("--rendered requires --adapter")
            report = rendered_parity(arguments.adapter, root)
            print(json.dumps(_plain(report), indent=2, sort_keys=True))
            return 0 if report["ok"] else 1
        if arguments.contract:
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
        from kingstack.checks import live_checks, overall, staged_checks
        if arguments.schedules:
            from kingstack.schedules import load_schedules
            load_schedules(root)
            print("schedules valid")
            return 0
        if arguments.memory:
            print("memory store is private and copy-only; live apply is not part of staged check")
            return 0
        if arguments.core:
            rows = [row for row in staged_checks(root) if row["adapter"] == "core"]
        elif arguments.mode == "live":
            rows = live_checks(root)
        else:
            rows = staged_checks(root)
        result = {"schema_version": 1, "overall": overall(rows), "rows": rows}
        print(json.dumps(result, indent=2, sort_keys=True) if arguments.json else result["overall"])
        return 0 if result["overall"] == "healthy" else 1
    if arguments.command == "render":
        root = Path(__file__).resolve().parents[2]
        try:
            bundle = render_bundle(arguments.adapter, root)
            skill_document = bundle_manifest(arguments.adapter, root)
            selected_path = arguments.print_file or arguments.check_file
            if selected_path is not None and selected_path not in bundle:
                raise RenderError(
                    "rendered bundle has no canonical path '{}'".format(selected_path)
                )
            if arguments.manifest:
                document = {
                    "schema_version": 1,
                    "adapter": arguments.adapter,
                    "upstreams": _plain(skill_document["upstreams"]),
                    "skills": _plain(skill_document["skills"]),
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
        except (RenderError, AdapterContractError, SkillCatalogError) as error:
            print("kingstack render: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "sync-upstream":
        root = Path(__file__).resolve().parents[2]
        if arguments.upstream == "headroom":
            from kingstack.headroom import HeadroomError, check_pin
            if arguments.bundle_manifest:
                sync_command.error("headroom has no skill bundle")
            try:
                report = check_pin(root, arguments.upstream_root or root.parent / "headroom")
                print(json.dumps({"schema_version": 1, "upstream": _plain(report)}, indent=2, sort_keys=True))
                return 0
            except HeadroomError as error:
                print("kingstack sync-upstream: {}".format(error), file=sys.stderr)
                return 2
        upstream_root = arguments.upstream_root or root.parent / "plugins"
        try:
            if arguments.bundle_manifest:
                print(json.dumps(_plain(bundle_manifest(arguments.adapter, root, upstream_root)), indent=2, sort_keys=True))
                return 0
            upstream_report = check_upstream(arguments.upstream, root, upstream_root)
            semantic_errors = {
                adapter: semantic_parity_errors(adapter, root, upstream_root)
                for adapter in ("claude", "codex")
            }
            failures = [
                "{}: {}".format(adapter, error)
                for adapter, errors in semantic_errors.items()
                for error in errors
            ]
            if failures:
                raise SkillCatalogError("; ".join(failures))
            if arguments.installed_root is not None:
                check_clobber_manifest(
                    arguments.adapter,
                    root,
                    arguments.installed_root,
                    arguments.installed_manifest.read_bytes(),
                    upstream_root=upstream_root,
                )
            print(json.dumps(_plain({"schema_version": 1, "upstream": upstream_report, "semantics": semantic_errors}), indent=2, sort_keys=True))
            return 0
        except (OSError, SkillCatalogError) as error:
            print("kingstack sync-upstream: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "memory":
        from kingstack.memory_migrate import migrate_claude
        from kingstack.memory_review import list_pending, promote, reject
        from kingstack.memory_store import MemoryStore
        memory_root = arguments.root if getattr(arguments, "root", None) else (Path.home() / ".kingstack" / "memory")
        try:
            if arguments.memory_command == "migrate-claude" and arguments.dry_run:
                from kingstack.memory_migrate import inventory_banks
                report = inventory_banks(arguments.claude_home or (Path.home() / ".claude"))
                print(json.dumps(_plain(report), indent=2, sort_keys=True))
                return 0
            store = MemoryStore.open(memory_root, repo_root=Path(__file__).resolve().parents[2])
            if arguments.memory_command == "list":
                print(json.dumps(list_pending(store, arguments.project), indent=2, sort_keys=True))
                return 0
            if arguments.memory_command == "show":
                match = next((item for item in list_pending(store) if item["id"] == arguments.candidate_id), None)
                if match is None:
                    raise ValueError("unknown pending candidate")
                print(json.dumps(match, indent=2, sort_keys=True))
                return 0
            if arguments.memory_command == "migrate-claude":
                report = migrate_claude(
                    arguments.claude_home or (Path.home() / ".claude"),
                    store,
                    apply=bool(arguments.apply),
                )
                print(json.dumps(_plain(report), indent=2, sort_keys=True))
                return 0
            if arguments.memory_command == "promote":
                path = promote(
                    store, arguments.candidate_id, arguments.name, arguments.memory_type,
                    arguments.description, arguments.body, arguments.actor,
                )
                print(str(path))
                return 0
            if arguments.memory_command == "recall":
                from kingstack.memory_context import recall
                print(recall(store, arguments.cwd or Path.cwd(), arguments.names))
                return 0
            if arguments.memory_command == "consolidate":
                from kingstack.memory_consolidate import consolidate
                print(json.dumps(consolidate(store), indent=2, sort_keys=True))
                return 0
            if arguments.memory_command == "harvest":
                from kingstack.memory_harvest import harvest
                created = harvest(
                    store,
                    arguments.inbox,
                    arguments.cwd or Path.cwd(),
                    arguments.adapter,
                )
                print(json.dumps(created, indent=2, sort_keys=True))
                return 0
            reject(store, arguments.candidate_id, arguments.reason, arguments.actor)
            return 0
        except Exception as error:
            print("kingstack memory: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "release":
        from kingstack.release import (
            ReleaseError,
            build_release,
            list_releases,
            rollback_release,
            select_release,
        )
        root = Path(__file__).resolve().parents[2]
        try:
            if arguments.build:
                result = build_release(arguments.adapter, root, arguments.runtime)
            elif arguments.list:
                result = list_releases(arguments.adapter, arguments.runtime)
            elif arguments.select:
                result = select_release(arguments.adapter, arguments.runtime, arguments.to)
            else:
                result = rollback_release(arguments.adapter, arguments.runtime, arguments.to)
            print(json.dumps(result, indent=2, sort_keys=True))
            return 0
        except (OSError, ReleaseError) as error:
            print("kingstack release: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "activate":
        from kingstack.activation import ActivationError, apply_activation, plan_activation
        root = Path(__file__).resolve().parents[2]
        try:
            plan = plan_activation(
                arguments.adapter,
                root,
                arguments.native_home,
                arguments.release,
                runtime=arguments.runtime,
            )
            if arguments.apply:
                result = apply_activation(plan, root, allow_live=True)
                print(json.dumps(_plain(result), indent=2, sort_keys=True))
                return 0
            print(json.dumps(plan, indent=2, sort_keys=True))
            return 0
        except ActivationError as error:
            print("kingstack activate: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "session":
        from kingstack.project_id import ProjectIdError, project_id
        from kingstack.session_store import SessionStore, SessionStoreError, default_root
        repo = Path(__file__).resolve().parents[2]
        sessions_root = arguments.root if getattr(arguments, "root", None) else default_root()
        try:
            if arguments.root is None and arguments.session_command in ("list", "show"):
                if not Path(sessions_root).exists():
                    if arguments.session_command == "list":
                        print("[]")
                        return 0
                    raise SessionStoreError("no session store; run kingstack setup")
            store = SessionStore.open(sessions_root, repo_root=repo)
            if arguments.session_command == "list":
                project = arguments.project
                if project is None and arguments.cwd is not None:
                    project = project_id(arguments.cwd)
                print(json.dumps(store.list_records(project), indent=2, sort_keys=True))
                return 0
            if arguments.session_command == "show":
                print(json.dumps(dict(store.show(arguments.session_id)), indent=2, sort_keys=True))
                return 0
            from kingstack.handoff import attach_session, packet, render_packet, write_packet
            record = store.show(arguments.session_id)
            existing = record.get("packet_path") or ""
            if existing and Path(existing).is_file() and not arguments.finish:
                print(Path(existing).read_text(encoding="utf-8"), end="")
                return 0
            finish = arguments.finish or record.get("finish_condition") or ""
            if not str(finish).strip():
                raise SessionStoreError(
                    "finish condition is required; pass --finish \"<done means>\""
                )
            cwd = arguments.cwd or Path.cwd()
            document = packet(
                str(finish),
                cwd,
                store=arguments.store,
                memory_root=arguments.memory_root,
            )
            packet_path = ""
            if arguments.out is None:
                print(render_packet(document), end="")
            else:
                packet_path = str(write_packet(arguments.out, document))
                print(packet_path)
            attach_session(
                document,
                cwd,
                packet_path=packet_path,
                session_key=record["id"],
                sessions_root=sessions_root,
            )
            return 0
        except (OSError, SessionStoreError, ProjectIdError) as error:
            print("kingstack session: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "handoff":
        from kingstack.handoff import (
            HandoffError,
            attach_session,
            packet,
            render_packet,
            write_packet,
        )
        from kingstack.project_id import ProjectIdError
        from kingstack.session_store import SessionStoreError
        try:
            cwd = arguments.cwd or Path.cwd()
            document = packet(
                arguments.finish,
                cwd,
                store=arguments.store,
                memory_root=arguments.memory_root,
            )
            packet_path = ""
            if arguments.out is None:
                print(render_packet(document), end="")
            else:
                packet_path = str(write_packet(arguments.out, document))
                print(packet_path)
            attach_session(
                document,
                cwd,
                packet_path=packet_path,
                session_key=arguments.session,
                sessions_root=arguments.sessions_root,
            )
            return 0
        except (HandoffError, SessionStoreError, ProjectIdError) as error:
            print("kingstack handoff: {}".format(error), file=sys.stderr)
            return 2
    if arguments.command == "headroom":
        from kingstack.headroom import HeadroomError, crush, default_store, retrieve, stats
        root = Path(__file__).resolve().parents[2]
        store = arguments.store or default_store()
        try:
            if arguments.headroom_command == "crush":
                if arguments.file is None:
                    text = sys.stdin.read()
                else:
                    text = arguments.file.read_text(encoding="utf-8")
                record = crush(text, store, root, tool=arguments.tool)
                print(record["notice"], end="")
                return 0
            if arguments.headroom_command == "retrieve":
                sys.stdout.write(retrieve(arguments.archive_id, store, root))
                return 0
            print(json.dumps(_plain(stats(store, root)), indent=2, sort_keys=True))
            return 0
        except (OSError, HeadroomError) as error:
            print("kingstack headroom: {}".format(error), file=sys.stderr)
            return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
