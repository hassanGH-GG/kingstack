"""Propose merges for near-duplicate promoted memories. Never auto-promote."""

from difflib import SequenceMatcher
from pathlib import Path
from typing import List, Mapping

from kingstack.memory_candidate import make_candidate
from kingstack.memory_review import list_pending
from kingstack.memory_store import MemoryStore


RATIO = 0.85


def _body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    _, marker, rest = text.partition("\n---\n")
    return (rest if marker else text).strip()


def consolidate(store: MemoryStore, actor: str = "setup") -> List[Mapping[str, object]]:
    pending_ids = {item["id"] for item in list_pending(store)}
    created = []
    projects = store.root / "projects"
    if not projects.is_dir():
        return created
    for bank in sorted(path for path in projects.iterdir() if path.is_dir()):
        memories = sorted((bank / "memories").glob("*.md")) if (bank / "memories").is_dir() else []
        for left, right in (
            (memories[i], memories[j])
            for i in range(len(memories))
            for j in range(i + 1, len(memories))
        ):
            if SequenceMatcher(None, _body(left), _body(right)).ratio() < RATIO:
                continue
            body = (
                "Near-duplicate memories. Propose merge or drop one.\n\n"
                "- {}\n- {}\n"
            ).format(left.name, right.name)
            candidate = make_candidate(
                "claude",
                bank.name,
                "consolidate-{}-{}".format(left.stem, right.stem),
                "consolidate {}".format(left.stem),
                "Near-duplicate promoted memories",
                body,
                "project",
            )
            if candidate["id"] in pending_ids:
                continue
            store.append_candidate(candidate)
            pending_ids.add(candidate["id"])
            created.append(candidate)
    return created
