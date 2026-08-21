"""Stop: upsert one memory candidate and never block the session."""

from datetime import datetime
import os
from pathlib import Path

from kingstack.hooks.inbox import Candidate, distill, human_prompts, log_error, one_line, upsert


def handle(event, runtime: Path) -> dict:
    runtime = Path(runtime)
    payload = event["payload"]
    transcript = payload.get("transcript_path") or ""
    session_id = event["session_id"]
    project = os.path.basename(str(event["project"]).rstrip("/")) or "-"
    if not transcript or not os.path.exists(transcript):
        log_error(runtime, "no transcript for session %s: %r" % (session_id, transcript))
        return {"blocked": False}
    found = distill(human_prompts(transcript))
    if not found:
        return {"blocked": False}
    kind, text, count = found
    upsert(
        runtime,
        Candidate(
            when=datetime.now().strftime("%Y-%m-%d %H:%M"),
            project=project,
            kind=kind,
            text=one_line(text),
            prompts=count,
            session=session_id[:8],
            transcript=transcript,
        ),
    )
    memory_root = os.environ.get("KINGSTACK_MEMORY_ROOT")
    if memory_root:
        try:
            from kingstack.memory_candidate import make_candidate
            from kingstack.memory_store import MemoryStore
            from kingstack.project_id import project_id
            store = MemoryStore.open(Path(memory_root))
            store.append_candidate(
                make_candidate(
                    event["agent"],
                    project_id(Path(event["project"])),
                    session_id,
                    kind,
                    one_line(text),
                    one_line(text),
                    "feedback" if kind == "correction" else "project",
                )
            )
        except Exception:
            pass
    try:
        from kingstack.session_store import record_from_hook
        record_from_hook(event, transcript=transcript)
    except Exception:
        pass
    return {"blocked": False}
