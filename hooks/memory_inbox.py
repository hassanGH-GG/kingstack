#!/usr/bin/env python3
"""Shared model and CLI for the memory-review inbox.

Both writers go through this module, so the line grammar lives in exactly one
place: the Stop hook (`session-memory-distiller.py`) upserts candidates, and the
`/memory-review` pass promotes or rejects them through the CLI below.

The inbox has two sections. Pending candidates sit under the header; a reviewed
one moves to a trailing `## Reviewed` section and keeps a ticked box. The tick is
what stops the hook re-offering a session it already saw, which matters because
Stop fires once per turn and a session stays live after review. Every write is an
upsert keyed on the short session id, and the whole read-modify-write runs under
flock so parallel sessions cannot clobber each other.

CLI:
    memory_inbox.py list [--json] [--all]
    memory_inbox.py promote --session ID8 --name slug --type TYPE \\
        --description TEXT --body-file PATH [--title TEXT] [--memory-dir DIR]
    memory_inbox.py reject --session ID8 [--session ID8 ...] [--reason TEXT]
"""
import argparse
import fcntl
import json
import os
import re
import sys

HOME = os.path.expanduser("~")
REVIEW_FILE = os.environ.get(
    "CLAUDE_MEMORY_REVIEW_FILE", os.path.join(HOME, ".claude", "memory-review.md")
)

HEADER = (
    "# Memory review inbox\n\n"
    "One candidate line per session, appended by the session-memory distiller\n"
    "(`~/.claude/hooks/session-memory-distiller.py`). Nothing here is memory yet.\n"
    "Run `/memory-review` to promote or reject candidates; reviewed lines move to\n"
    "the `## Reviewed` section at the bottom and are never offered again.\n\n"
)
REVIEWED_MARKER = "## Reviewed"

MEMORY_TYPES = ("user", "feedback", "project", "reference")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
FIELD_SEP = " | "

# The harness marks where a prompt came from. These three are human-authored:
# typed interactively, accepted from a suggestion, or passed to `claude -p`.
# Anything else in a `user` row is a tool result, a system reminder, a skill body,
# or an interrupt notice, none of which is worth remembering.
# Only prompts a human typed into a session. `sdk` was included when headless runs were
# rare and human-initiated; it now covers sweeps, box-task, probes and agent-to-agent calls,
# which the framework fires constantly, so it produces noise rather than memory. Dropped.
HUMAN_PROMPT_SOURCES = {"typed", "suggestion_accepted"}

# Belt and braces for anything that still arrives looking like an instruction to an agent
# rather than a request from a person. A role assignment or a standing-order opener is the
# tell: nobody types "You are an expert code reviewer" at their own session.
AGENT_PREAMBLE = re.compile(
    r"^(?:you are (?:a|an|the)\b|you are (?:working|running)\b|your (?:job|task) is\b"
    r"|act as\b|remember this fact for later\b)",
    re.IGNORECASE,
)


class InboxError(Exception):
    pass


class Candidate(object):
    """One inbox line. Text and paths never contain `|`, so the pipe-separated
    fields round-trip exactly."""

    FIELDS = 7

    def __init__(self, when, project, kind, text, prompts, session, transcript,
                 reviewed=False, outcome=None):
        self.when = when
        self.project = project
        self.kind = kind
        self.text = text
        self.prompts = prompts
        self.session = session
        self.transcript = transcript
        self.reviewed = reviewed
        self.outcome = outcome

    @property
    def key(self):
        return FIELD_SEP + self.session + FIELD_SEP

    @classmethod
    def parse(cls, line):
        stripped = line.strip()
        if not stripped.startswith("- ["):
            return None
        box, _, rest = stripped[2:].partition("] ")
        reviewed = box.strip("[ ").lower() == "x"
        parts = rest.split(FIELD_SEP)
        if len(parts) < cls.FIELDS:
            return None
        outcome = FIELD_SEP.join(parts[cls.FIELDS:]) or None
        when, project, kind, text, prompts, session, transcript = parts[: cls.FIELDS]
        count = re.match(r"(\d+)", prompts.strip())
        return cls(
            when.strip(), project, kind, text, int(count.group(1)) if count else 0,
            session, transcript, reviewed=reviewed, outcome=outcome,
        )

    def render(self):
        fields = [
            self.when, self.project, self.kind, self.text,
            "%d prompt%s" % (self.prompts, "" if self.prompts == 1 else "s"),
            self.session, self.transcript,
        ]
        if self.outcome:
            fields.append(self.outcome)
        return "- [%s] %s\n" % ("x" if self.reviewed else " ", FIELD_SEP.join(fields))

    def routing(self):
        """Derive the memory bank from `<profile>/projects/<slug>/<id>.jsonl`.

        The transcript path is the only field that names both the profile root and
        the project, so a candidate captured under `~/.claude-personal` promotes
        into that profile's bank rather than the current session's.
        """
        parts = os.path.abspath(self.transcript).split(os.sep)
        if len(parts) >= 4 and parts[-3] == "projects":
            root = os.sep.join(parts[:-3])
            slug = parts[-2]
            return {
                "profile_root": root,
                "project_slug": slug,
                "memory_dir": os.path.join(root, "projects", slug, "memory"),
            }
        return {"profile_root": None, "project_slug": None, "memory_dir": None}

    def as_dict(self):
        data = {
            "when": self.when,
            "project": self.project,
            "kind": self.kind,
            "text": self.text,
            "prompts": self.prompts,
            "session": self.session,
            "transcript": self.transcript,
            "reviewed": self.reviewed,
            "outcome": self.outcome,
        }
        data.update(self.routing())
        return data


class Inbox(object):
    def __init__(self, header, pending, reviewed):
        self.header = header or HEADER
        self.pending = pending
        self.reviewed = reviewed

    @classmethod
    def parse(cls, text):
        """The section marker counts only as a whole line. The header prose names
        `## Reviewed` to explain itself, and matching that would swallow every
        pending line into the reviewed section."""
        header_lines, pending, reviewed = [], [], []
        in_reviewed = False
        for line in text.splitlines(True):
            if line.strip() == REVIEWED_MARKER:
                in_reviewed = True
                continue
            candidate = Candidate.parse(line)
            if candidate is None:
                if not (pending or reviewed or in_reviewed):
                    header_lines.append(line)
                continue
            candidate.reviewed = candidate.reviewed or in_reviewed
            (reviewed if candidate.reviewed else pending).append(candidate)
        return cls("".join(header_lines), pending, reviewed)

    def render(self):
        out = [self.header.rstrip("\n") + "\n\n"]
        out.extend(c.render() for c in self.pending)
        if self.reviewed:
            out.append("\n%s\n\n" % REVIEWED_MARKER)
            out.extend(c.render() for c in self.reviewed)
        return "".join(out)

    def find(self, session):
        for candidate in self.pending + self.reviewed:
            if candidate.session == session:
                return candidate
        return None

    def mark_reviewed(self, session, outcome):
        candidate = self.find(session)
        if candidate is None:
            raise InboxError("no candidate for session %s in %s" % (session, REVIEW_FILE))
        candidate.reviewed = True
        candidate.outcome = outcome
        self.pending = [c for c in self.pending if c is not candidate]
        self.reviewed = [c for c in self.reviewed if c is not candidate] + [candidate]
        return candidate


def edit_inbox(mutate, write=True):
    """Run `mutate(inbox)` under an exclusive lock and return its value. Writing
    back is unconditional when `write`, so the file is also normalized on every
    pass; the lock spans the whole read-modify-write."""
    fd = os.open(REVIEW_FILE, os.O_RDWR | os.O_CREAT, 0o644)
    with os.fdopen(fd, "r+") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            inbox = Inbox.parse(fh.read())
            result = mutate(inbox)
            if write:
                fh.seek(0)
                fh.write(inbox.render())
                fh.truncate()
            return result
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load():
    return edit_inbox(lambda inbox: inbox, write=False)


def upsert(candidate):
    """Add or refresh this session's pending line. A reviewed session keeps its
    ticked line, so promoting a candidate mid-session cannot resurrect it."""

    def mutate(inbox):
        existing = inbox.find(candidate.session)
        if existing is not None and existing.reviewed:
            return
        if existing is not None:
            inbox.pending = [candidate if c is existing else c for c in inbox.pending]
        else:
            inbox.pending.append(candidate)

    return edit_inbox(mutate)


def prompt_text(row):
    """Return the text of a human-authored prompt row, or None."""
    if row.get("type") != "user" or row.get("isSidechain") or row.get("isMeta"):
        return None
    if row.get("promptSource") not in HUMAN_PROMPT_SOURCES:
        return None
    content = row.get("message", {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        )
    else:
        return None
    # Slash-command invocations arrive wrapped in harness tags; keep the command.
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    if not text or AGENT_PREAMBLE.match(text):
        return None
    return text


def human_prompts(transcript):
    """Every prompt Hassan authored in a session, oldest first."""
    prompts = []
    with open(transcript, "r", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            text = prompt_text(row)
            if text:
                prompts.append(text)
    return prompts


def memory_filename(mem_type, name):
    return "%s_%s.md" % (mem_type, name.replace("-", "_"))


def write_memory_file(memory_dir, mem_type, name, description, body, session,
                      transcript):
    os.makedirs(memory_dir, exist_ok=True)
    path = os.path.join(memory_dir, memory_filename(mem_type, name))
    front = [
        "---",
        "name: %s" % name,
        "description: %s" % json.dumps(description),
        "metadata:",
        "  type: %s" % mem_type,
        "  originSessionId: %s" % session,
        "  originTranscript: %s" % transcript,
        "---",
        "",
    ]
    with open(path, "w") as fh:
        fh.write("\n".join(front) + "\n" + body.strip() + "\n")
    return path


def index_upsert(memory_dir, filename, title, hook):
    """Keep exactly one MEMORY.md pointer per memory file."""
    path = os.path.join(memory_dir, "MEMORY.md")
    line = "- [%s](%s) — %s\n" % (title, filename, hook)
    existing = ""
    if os.path.exists(path):
        with open(path) as fh:
            existing = fh.read()
    if not existing.strip():
        existing = "# Memory Index\n\n"
    lines = existing.splitlines(True)
    target = "](%s)" % filename
    for i, prev in enumerate(lines):
        if prev.startswith("- [") and target in prev:
            lines[i] = line
            break
    else:
        if not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append(line)
    with open(path, "w") as fh:
        fh.write("".join(lines))
    return path


def cmd_list(args):
    inbox = load()
    rows = inbox.pending + (inbox.reviewed if args.all else [])
    if args.json:
        json.dump([c.as_dict() for c in rows], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0
    if not rows:
        print("inbox empty: no pending candidates in %s" % REVIEW_FILE)
        return 0
    for c in rows:
        print("%s  %-10s %-10s %2d  %s" % (
            c.session, c.project, c.kind, c.prompts, c.text[:90]))
    return 0


def cmd_show(args):
    """Print a candidate's real prompts. The inbox text is one truncated prompt,
    too thin to draft a fact from."""
    candidate = load().find(args.session)
    if candidate is None:
        raise InboxError("no candidate for session %s" % args.session)
    routing = candidate.routing()
    print("session     %s (%s, %s)" % (candidate.session, candidate.project, candidate.kind))
    print("captured    %s" % candidate.when)
    print("memory dir  %s" % routing["memory_dir"])
    print("transcript  %s" % candidate.transcript)
    if candidate.outcome:
        print("outcome     %s" % candidate.outcome)
    if not os.path.exists(candidate.transcript):
        print("\ntranscript is gone; draft from the inbox text alone")
        return 0
    prompts = human_prompts(candidate.transcript)
    print("\n%d human prompt%s:" % (len(prompts), "" if len(prompts) == 1 else "s"))
    for i, text in enumerate(prompts, 1):
        if args.chars and len(text) > args.chars:
            text = text[: args.chars] + "…"
        print("\n%2d. %s" % (i, text))
    return 0


def cmd_promote(args):
    if args.type not in MEMORY_TYPES:
        raise InboxError("--type must be one of %s" % ", ".join(MEMORY_TYPES))
    if not NAME_RE.match(args.name):
        raise InboxError("--name must be kebab-case: %r" % args.name)
    description = " ".join(args.description.split())
    if not description:
        raise InboxError("--description is empty")
    body = (sys.stdin.read() if args.body_file == "-"
            else open(args.body_file).read())
    if not body.strip():
        raise InboxError("body is empty")
    if args.type in ("feedback", "project") and "**Why:**" not in body:
        raise InboxError("a %s memory needs a **Why:** line" % args.type)
    if args.type == "feedback" and "**How to apply:**" not in body:
        raise InboxError("a feedback memory needs a **How to apply:** line")

    inbox = load()
    candidate = inbox.find(args.session)
    if candidate is None:
        raise InboxError("no candidate for session %s" % args.session)
    memory_dir = args.memory_dir or candidate.routing()["memory_dir"]
    if not memory_dir:
        raise InboxError(
            "cannot derive a memory bank from %s; pass --memory-dir"
            % candidate.transcript)

    path = write_memory_file(memory_dir, args.type, args.name, description, body,
                             candidate.session, candidate.transcript)
    filename = os.path.basename(path)
    title = args.title or args.name.replace("-", " ")
    index = index_upsert(memory_dir, filename, title, description)
    edit_inbox(lambda ib: ib.mark_reviewed(args.session, "promoted: %s" % filename))
    print("memory  %s" % path)
    print("index   %s" % index)
    print("inbox   %s cleared from pending" % args.session)
    return 0


def cmd_reject(args):
    reason = " ".join((args.reason or "not memory-worthy").split())
    for session in args.session:
        edit_inbox(lambda ib, s=session: ib.mark_reviewed(s, "rejected: %s" % reason))
        print("inbox   %s rejected (%s)" % (session, reason))
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="show pending candidates")
    p_list.add_argument("--json", action="store_true")
    p_list.add_argument("--all", action="store_true", help="include reviewed lines")
    p_list.set_defaults(func=cmd_list)

    p_show = sub.add_parser("show", help="print one candidate's human prompts")
    p_show.add_argument("--session", required=True)
    p_show.add_argument("--chars", type=int, default=600,
                        help="truncate each prompt (0 for full text)")
    p_show.set_defaults(func=cmd_show)

    p_promote = sub.add_parser("promote", help="write a memory file and clear the line")
    p_promote.add_argument("--session", required=True)
    p_promote.add_argument("--name", required=True, help="kebab-case memory slug")
    p_promote.add_argument("--type", required=True, choices=MEMORY_TYPES)
    p_promote.add_argument("--description", required=True)
    p_promote.add_argument("--body-file", required=True, help="path, or - for stdin")
    p_promote.add_argument("--title", help="MEMORY.md link text")
    p_promote.add_argument("--memory-dir", help="override the derived memory bank")
    p_promote.set_defaults(func=cmd_promote)

    p_reject = sub.add_parser("reject", help="clear candidates without promoting")
    p_reject.add_argument("--session", required=True, action="append")
    p_reject.add_argument("--reason")
    p_reject.set_defaults(func=cmd_reject)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except InboxError as exc:
        sys.stderr.write("memory-review: %s\n" % exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
