#!/usr/bin/env python3
"""Stop hook: keep one candidate memory line per session in a review inbox.

Reads the Stop-hook JSON on stdin, scans the session transcript for prompts the
human actually typed, and writes a single line to the review file. Nothing is
promoted to real memory here -- this is an inbox a later pass distills.

Stop fires at the end of every turn, not only at session end, so the write is an
upsert keyed on the session id: the line converges on the session's latest state
however many times the hook runs, and parallel sessions cannot interleave. The
line grammar and the locking live in `memory_inbox.py`, shared with the
`/memory-review` pass that promotes candidates.

Contract: always exit 0. A memory tool must never be able to block a session
from ending.
"""
import json
import os
import re
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_inbox  # noqa: E402  (hooks run from the project cwd, not this dir)

HOME = os.path.expanduser("~")
ERROR_LOG = os.path.join(HOME, ".claude", "memory-review.error.log")

CORRECTION = re.compile(
    r"(?:^\s*(?:no|nope|wrong|stop|actually)\b"
    r"|\bdon'?t\b|\bdo not\b|\bnever\b|\binstead\b|\bnot what i\b"
    r"|\bi said\b|\byou (?:should have|forgot|missed|broke)\b"
    r"|\bwhy did you\b|\brevert\b|\bundo\b)",
    re.IGNORECASE,
)

MAX_TEXT = 200


def log_error(msg):
    try:
        with open(ERROR_LOG, "a") as fh:
            fh.write("%s %s\n" % (datetime.now().isoformat(timespec="seconds"), msg))
    except Exception:
        pass


def one_line(text):
    text = text.replace("|", "/")
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1].rstrip() + "…"
    return text


def distil(prompts):
    """Pick the single most memory-worthy prompt of the session.

    Corrections are the highest-value continual-learning signal, so the latest
    correction wins; otherwise the opening prompt stands in as session intent.
    """
    if not prompts:
        return None
    corrections = [p for p in prompts if CORRECTION.search(p)]
    if corrections:
        return "correction", corrections[-1], len(prompts)
    return "goal", prompts[0], len(prompts)


def main():
    raw = sys.stdin.read()
    payload = json.loads(raw) if raw.strip() else {}
    transcript = payload.get("transcript_path") or ""
    session_id = payload.get("session_id") or "unknown"
    cwd = payload.get("cwd") or os.getcwd()

    if not transcript or not os.path.exists(transcript):
        log_error("no transcript for session %s: %r" % (session_id, transcript))
        return

    found = distil(memory_inbox.human_prompts(transcript))
    if not found:
        return
    kind, text, count = found

    candidate = memory_inbox.Candidate(
        when=datetime.now().strftime("%Y-%m-%d %H:%M"),
        project=os.path.basename(cwd.rstrip("/")) or "-",
        kind=kind,
        text=one_line(text),
        prompts=count,
        session=session_id[:8],
        transcript=transcript,
    )
    memory_inbox.upsert(candidate)


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:  # never block a session from ending
        log_error("%s: %s" % (type(exc).__name__, exc))
    sys.exit(0)
