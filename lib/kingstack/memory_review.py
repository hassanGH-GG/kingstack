"""Human-gated promotion and rejection of shared memory candidates."""

import json
from pathlib import Path
from typing import List, Mapping, Optional

from kingstack.memory_store import MemoryStore, _atomic_write
from kingstack.secret_filter import reject_if_secret


class MemoryReviewError(ValueError):
    """Raised when a review action is invalid."""


def list_pending(store: MemoryStore, project_id: Optional[str] = None) -> List[Mapping[str, object]]:
    reviewed = {
        json.loads(line)["candidate_id"]
        for line in (store.root / "reviews.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    pending = []
    for line in (store.root / "inbox.jsonl").read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if item["id"] in reviewed:
            continue
        if project_id and item.get("project_id") != project_id:
            continue
        pending.append(item)
    return pending


def promote(
    store: MemoryStore,
    candidate_id: str,
    name: str,
    memory_type: str,
    description: str,
    body: str,
    actor: str,
) -> Path:
    reject_if_secret("\n".join((name, description, body)))
    candidate = next((item for item in list_pending(store) if item["id"] == candidate_id), None)
    if candidate is None:
        raise MemoryReviewError("unknown pending candidate")
    bank = store.bank(candidate["project_id"])
    filename = "{}_{}.md".format(memory_type, name.replace("-", "_"))
    path = bank / "memories" / filename
    path.parent.mkdir(mode=0o700, exist_ok=True)
    text = (
        "---\nname: {}\ndescription: {}\nmetadata:\n  type: {}\n  origin: {}\n---\n\n{}\n"
    ).format(name, json.dumps(description), memory_type, candidate_id, body.strip())
    _atomic_write(path, text.encode("utf-8"))
    index = bank / "MEMORY.md"
    pointer = "- [{}](memories/{}) — {}\n".format(name, filename, description)
    current = index.read_text(encoding="utf-8") if index.exists() else "# Memory Index\n\n"
    if filename not in current:
        _atomic_write(index, (current.rstrip() + "\n" + pointer).encode("utf-8"))
    store.review(candidate_id, "promote", actor, {"path": str(path)})
    return path


def reject(store: MemoryStore, candidate_id: str, reason: str, actor: str) -> Mapping[str, object]:
    return store.review(candidate_id, "reject", actor, {"reason": reason})
