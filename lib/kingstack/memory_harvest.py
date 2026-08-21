"""Turn inbox corrections into memory candidates. Same approve gate as Stop."""

from pathlib import Path
from typing import List, Mapping, Optional

from kingstack.hooks.inbox import Inbox
from kingstack.memory_candidate import make_candidate
from kingstack.memory_review import list_pending
from kingstack.memory_store import MemoryStore
from kingstack.project_id import project_identity


def harvest(
    store: MemoryStore,
    inbox_file: Path,
    cwd: Path,
    adapter: str = "claude",
) -> List[Mapping[str, object]]:
    path = Path(inbox_file)
    if not path.is_file():
        return []
    inbox = Inbox.parse(path.read_text(encoding="utf-8"))
    cwd = Path(cwd)
    pending_ids = {item["id"] for item in list_pending(store)}
    created = []
    for item in inbox.pending:
        if item.kind != "correction":
            continue
        identity = _identity_for_item(cwd, item.project)
        store.register_project(identity)
        candidate = make_candidate(
            adapter,
            identity.id,
            item.session,
            item.kind,
            item.text,
            item.text,
            "feedback",
        )
        if candidate["id"] in pending_ids:
            continue
        store.append_candidate(candidate)
        pending_ids.add(candidate["id"])
        created.append(candidate)
    return created


def _identity_for_item(cwd: Path, project: str):
    if cwd.name == project:
        return project_identity(cwd)
    sibling = cwd.parent / project
    if sibling.is_dir():
        return project_identity(sibling)
    return project_identity(cwd)
