"""Bounded session-index injection. Pointers only."""

from pathlib import Path

from kingstack.project_id import ProjectIdError, project_identity
from kingstack.session_store import SessionStore


def project_index(store: SessionStore, cwd: Path, max_bytes: int = 12000) -> str:
    try:
        identity = project_identity(Path(cwd))
    except (OSError, ProjectIdError):
        return ""
    rows = store.current(identity.id)
    if not rows:
        return ""
    lines = [
        "<session_index>Project {} has {} recent session(s). "
        "Pointers only. Continue with `kingstack session continue <id>`. "
        "Do not open another host's transcript.".format(identity.id, len(rows)),
        "",
    ]
    for row in rows:
        prompts = row.get("last_prompts") or []
        hint = prompts[-1] if prompts else "(no prompts yet)"
        finish = row.get("finish_condition") or "(none)"
        lines.append(
            "- [{}] {} {} · finish: {} · {}".format(
                row.get("adapter"),
                row.get("id"),
                row.get("status"),
                finish,
                hint,
            )
        )
    lines.append("</session_index>")
    text = "\n".join(lines)
    encoded = text.encode("utf-8")
    if len(encoded) > max_bytes:
        text = encoded[: max_bytes - 80].decode("utf-8", errors="ignore")
        text += "\n[truncated; use kingstack session list]\n</session_index>"
    return text
