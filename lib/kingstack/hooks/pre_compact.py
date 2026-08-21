"""PreCompact: checkpoint load-bearing facts and return the preserve directive."""

import os
from datetime import datetime
from pathlib import Path
import subprocess

from kingstack.hooks.inbox import human_prompts


PRESERVE = (
    "PRESERVE VERBATIM in the summary, these outrank narrative: (1) the current "
    "finish condition, done means, exactly as last stated; (2) every file path "
    "edited or created this session and whether it is committed and pushed; "
    "(3) open decisions and anything Hassan corrected, in his words; (4) any "
    "command or step that was about to run next; (5) unpushed or uncommitted "
    "state named in the transcript. Drop pleasantries and process narration "
    "first, never these. (6) headroom archive ids and "
    "`kingstack headroom retrieve <id>`; drop raw tool blobs, keep the digest."
)


def handle(event, runtime: Path) -> dict:
    runtime = Path(runtime)
    payload = event["payload"]
    session = event["session_id"][:8]
    project = event["project"]
    transcript = payload.get("transcript_path") or ""
    directory = runtime / "logs" / "compaction-checkpoints"
    directory.mkdir(parents=True, exist_ok=True)
    os.chmod(directory, 0o700)
    lines = [
        "# compaction checkpoint {} session {} cwd {}".format(
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"), session, project
        )
    ]
    if _is_git(project):
        lines.append("## git state at compaction")
        status = _run_git(project, ["status", "--short"])
        lines.extend(status.splitlines()[:20])
        unpushed = _run_git(project, ["log", "--oneline", "@{u}..HEAD"])
        count = len([line for line in unpushed.splitlines() if line.strip()])
        lines.append("unpushed: {} commit(s)".format(count))
    if transcript and os.path.exists(transcript):
        lines.append("## last human prompts before compaction")
        for text in human_prompts(transcript)[-6:]:
            lines.append("- {}".format(text.replace("\n", " ")[:200]))
    checkpoint = directory / "{}.md".format(session)
    checkpoint.write_text("\n".join(lines) + "\n", encoding="utf-8")
    os.chmod(checkpoint, 0o600)
    try:
        from kingstack.session_store import record_from_hook
        record_from_hook(
            event,
            status="compacted",
            transcript=transcript,
            checkpoint=str(checkpoint),
        )
    except Exception:
        pass
    extra = PRESERVE
    store = os.environ.get("KINGSTACK_HEADROOM_ROOT")
    if store:
        from kingstack.headroom import live_ids
        ids = live_ids(Path(store))
        if ids:
            extra += " Live ids: {}.".format(", ".join(ids))
    memory_root = os.environ.get("KINGSTACK_MEMORY_ROOT")
    if memory_root:
        try:
            from kingstack.memory_context import session_index
            from kingstack.memory_store import MemoryStore
            index = session_index(MemoryStore.open(Path(memory_root)), event["project"])
            if index:
                extra += "\n\n" + index
        except Exception:
            pass
    return {"additionalContext": extra}


def _is_git(project: str) -> bool:
    return bool(project) and _run_git(project, ["rev-parse", "--git-dir"]) != ""


def _run_git(project: str, args):
    if not project:
        return ""
    try:
        result = subprocess.run(
            ["git", "-C", project, *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
    except OSError:
        return ""
    return result.stdout if result.returncode == 0 else ""
