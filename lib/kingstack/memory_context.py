"""Bounded shared-memory injection for any adapter session."""

from pathlib import Path
from typing import List

from kingstack.memory_store import MemoryStore
from kingstack.project_id import project_identity


def session_index(store: MemoryStore, cwd: Path, max_bytes: int = 12000) -> str:
    identity = project_identity(Path(cwd))
    try:
        bank = store.bank(identity.id)
    except Exception:
        return ""
    index = (bank / "MEMORY.md").read_text(encoding="utf-8")
    header = (
        "<shared_memory origin=\"kingstack\">Project {} has curated shared "
        "memory. This is not native adapter memory. Recall a full body with "
        "`kingstack memory recall`.\n\n"
    ).format(identity.id)
    text = header + index
    if len(text.encode("utf-8")) > max_bytes:
        text = text.encode("utf-8")[: max_bytes - 80].decode("utf-8", errors="ignore")
        text += "\n[truncated; use kingstack memory recall]\n"
    return text + "</shared_memory>"


def recall(store: MemoryStore, cwd: Path, names: List[str]) -> str:
    identity = project_identity(Path(cwd))
    bank = store.bank(identity.id)
    chunks = []
    for name in names:
        matches = list((bank / "memories").glob("*{}*".format(name.replace("-", "_"))))
        for path in matches:
            chunks.append(path.read_text(encoding="utf-8"))
    return "\n\n".join(chunks)
