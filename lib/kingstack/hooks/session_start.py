"""SessionStart: inject the operating contract, pending inbox, and usage line."""

from datetime import datetime, timedelta
import os
from pathlib import Path


def handle(event, runtime: Path) -> dict:
    runtime = Path(runtime)
    contract = (runtime / "hooks/poteto-mode-context.md").read_text(encoding="utf-8")
    context = contract.rstrip("\n")
    inbox = runtime / "memory-review.md"
    if inbox.is_file():
        pending = sum(
            1 for line in inbox.read_text(encoding="utf-8").splitlines()
            if line.startswith("- [ ]")
        )
        if pending:
            last = datetime.fromtimestamp(inbox.stat().st_mtime).strftime("%Y-%m-%d")
            context += (
                "\n\n<memory_inbox>{} memory candidate(s) are waiting in {} "
                "(last change {}). If Hassan is not mid-task, mention it once "
                "in your first reply and offer /memory-review; never run it "
                "unasked.</memory_inbox>"
            ).format(pending, inbox, last)
    ledger = runtime / "usage-ledger.csv"
    if ledger.is_file():
        yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        turns = tokens = usd = 0
        for line in ledger.read_text(encoding="utf-8").splitlines()[1:]:
            fields = line.split(",")
            if len(fields) < 9 or fields[0] != yesterday:
                continue
            turns += int(fields[3])
            tokens += int(fields[4]) + int(fields[5]) + int(fields[6])
            usd += float(fields[8])
        if turns:
            context += (
                "\n\n<usage>yesterday: {} turns, {}k ctx/turn, ~${:.0f} "
                "list-equivalent. The ruler's session-weight rule applies: "
                "past ~150k context, propose /clear; bulk to subagents; "
                "polling is never an LLM turn.</usage>"
            ).format(turns, int(tokens / turns / 1000), usd)
    identity = os.environ.get("KINGSTACK_IDENTITY")
    if identity == "personal":
        context += (
            "\n\n<identity>This machine is personal identity. Use poteto-mode. "
            "Do not run king-mode unless asked. You do not have Hassan's memory.</identity>"
        )
    elif identity == "hassan":
        context += (
            "\n\n<identity>Run king-mode with poteto-mode on any non-trivial task.</identity>"
        )
    memory_root = Path(os.environ["KINGSTACK_MEMORY_ROOT"]) if os.environ.get("KINGSTACK_MEMORY_ROOT") else None
    if memory_root is not None:
        try:
            from kingstack.memory_context import session_index
            from kingstack.memory_store import MemoryStore
            shared = session_index(MemoryStore.open(memory_root), event["project"])
            if shared:
                context += "\n\n" + shared
        except Exception:
            pass
    store = os.environ.get("KINGSTACK_HEADROOM_ROOT")
    if store:
        from kingstack.headroom import live_ids
        ids = live_ids(Path(store))
        if ids:
            context += (
                "\n\n<headroom>Live archive ids: {}. "
                "Drop raw blobs. Retrieve with `kingstack headroom retrieve <id>`.</headroom>"
            ).format(", ".join(ids))
    try:
        from kingstack.session_store import record_from_hook
        record_from_hook(event, status="live")
    except Exception:
        pass
    sessions_root = os.environ.get("KINGSTACK_SESSIONS_ROOT")
    if sessions_root:
        try:
            from kingstack.session_context import project_index
            from kingstack.session_store import SessionStore
            shared = project_index(SessionStore.open(Path(sessions_root)), event["project"])
            if shared:
                context += "\n\n" + shared
        except Exception:
            pass
    return {"additionalContext": context}
