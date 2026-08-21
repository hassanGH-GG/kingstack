"""Write a packet another adapter can open. Does not pretend Codex can spawn."""

import json
import subprocess
from pathlib import Path
from typing import List, Mapping, Optional

from kingstack.headroom import default_store, live_ids
from kingstack.project_id import project_identity


class HandoffError(ValueError):
    """Raised when a handoff packet cannot be written."""


def _git(cwd: Path, arguments: List[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(cwd), *arguments],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""


def packet(
    finish: str,
    cwd: Path,
    store: Optional[Path] = None,
    memory_root: Optional[Path] = None,
) -> Mapping[str, object]:
    if not finish.strip():
        raise HandoffError("finish condition is required")
    cwd = Path(cwd)
    status = _git(cwd, ["status", "--short"])
    branch = _git(cwd, ["rev-parse", "--abbrev-ref", "HEAD"]).strip()
    unpushed = _git(cwd, ["log", "--oneline", "@{u}..HEAD"])
    paths = [line[3:] for line in status.splitlines() if line[3:]]
    names = []
    if memory_root is not None:
        try:
            from kingstack.memory_store import MemoryStore
            bank = MemoryStore.open(memory_root).bank(project_identity(cwd).id)
            index = (bank / "MEMORY.md").read_text(encoding="utf-8")
            names = [
                line.split("]")[0][2:]
                for line in index.splitlines()
                if line.startswith("- [")
            ]
        except Exception:
            names = []
    headroom = []
    if store is not None:
        headroom = live_ids(store)
    elif default_store().is_dir():
        headroom = live_ids(default_store())
    return {
        "schema": 1,
        "adapter": "codex",
        "finish_condition": finish.strip(),
        "branch": branch,
        "dirty_paths": paths,
        "unpushed": len([line for line in unpushed.splitlines() if line.strip()]),
        "headroom_ids": headroom,
        "memory_names": names,
        "unsupported": ["host spawn", "loop primitive"],
    }


def render_packet(document: Mapping[str, object]) -> str:
    lines = [
        "# kingstack handoff",
        "",
        "Open this file and continue. Do not invent host spawn or a loop primitive.",
        "",
        "- finish: {}".format(document["finish_condition"]),
        "- branch: {}".format(document["branch"] or "(unknown)"),
        "- unpushed: {}".format(document["unpushed"]),
        "- dirty: {}".format(", ".join(document["dirty_paths"]) or "(clean)"),
        "- headroom: {}".format(", ".join(document["headroom_ids"]) or "(none)"),
        "- memory: {}".format(", ".join(document["memory_names"]) or "(none)"),
        "",
        "```json",
        json.dumps(document, indent=2, sort_keys=True),
        "```",
        "",
    ]
    return "\n".join(lines)


def write_packet(path: Path, document: Mapping[str, object]) -> Path:
    path = Path(path)
    path.write_text(render_packet(document), encoding="utf-8")
    return path


def attach_session(
    document: Mapping[str, object],
    cwd: Path,
    packet_path: str = "",
    session_key: Optional[str] = None,
    sessions_root: Optional[Path] = None,
) -> Optional[Mapping[str, object]]:
    from kingstack.session_store import mark_handoff
    return mark_handoff(
        cwd,
        str(document["finish_condition"]),
        packet_path=packet_path,
        session_key=session_key,
        root=sessions_root,
    )
