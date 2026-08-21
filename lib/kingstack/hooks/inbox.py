"""Capture-only memory inbox used by the Stop handler."""

from datetime import datetime
import fcntl
import json
import os
from pathlib import Path
import re


HEADER = (
    "# Memory review inbox\n\n"
    "One candidate line per session, appended by the session-memory distiller.\n"
    "Nothing here is memory yet.\n\n"
)
REVIEWED_MARKER = "## Reviewed"
FIELD_SEP = " | "
HUMAN_PROMPT_SOURCES = {"typed", "suggestion_accepted"}
AGENT_PREAMBLE = re.compile(
    r"^(?:you are (?:a|an|the)\b|you are (?:working|running)\b|your (?:job|task) is\b"
    r"|act as\b|remember this fact for later\b)",
    re.IGNORECASE,
)
CORRECTION = re.compile(
    r"(?:^\s*(?:no|nope|wrong|stop|actually)\b"
    r"|\bdon'?t\b|\bdo not\b|\bnever\b|\binstead\b|\bnot what i\b"
    r"|\bi said\b|\byou (?:should have|forgot|missed|broke)\b"
    r"|\bwhy did you\b|\brevert\b|\bundo\b)",
    re.IGNORECASE,
)
MAX_TEXT = 200
PROBE_WORDS = 8
HEALTH_PROBE = re.compile(
    r"(?:^is \w[\w-]* working\b|\bprove it\b|\bdo not change anything\b|\bdo not edit\b)",
    re.IGNORECASE,
)


class Candidate:
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


class Inbox:
    def __init__(self, header, pending, reviewed):
        self.header = header or HEADER
        self.pending = pending
        self.reviewed = reviewed

    @classmethod
    def parse(cls, text):
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
        out.extend(candidate.render() for candidate in self.pending)
        if self.reviewed:
            out.append("\n%s\n\n" % REVIEWED_MARKER)
            out.extend(candidate.render() for candidate in self.reviewed)
        return "".join(out)

    def find(self, session):
        for candidate in self.pending + self.reviewed:
            if candidate.session == session:
                return candidate
        return None


def inbox_path(runtime: Path) -> Path:
    return Path(runtime) / "memory-review.md"


def pending_count(runtime: Path) -> int:
    path = inbox_path(runtime)
    if not path.is_file():
        return 0
    return sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.startswith("- [ ]"))


def one_line(text):
    text = text.replace("|", "/")
    if len(text) > MAX_TEXT:
        text = text[: MAX_TEXT - 1].rstrip() + "…"
    return text


def is_probe(text, count):
    if count != 1:
        return False
    stripped = text.strip()
    if stripped.endswith("?"):
        return True
    if HEALTH_PROBE.search(stripped):
        return True
    return len(stripped.split()) <= PROBE_WORDS


def distill(prompts):
    if not prompts:
        return None
    if is_probe(prompts[0], len(prompts)):
        return None
    corrections = [item for item in prompts if CORRECTION.search(item)]
    if corrections:
        return "correction", corrections[-1], len(prompts)
    return "goal", prompts[0], len(prompts)


def prompt_text(row):
    if row.get("type") != "user" or row.get("isSidechain") or row.get("isMeta"):
        return None
    if row.get("promptSource") not in HUMAN_PROMPT_SOURCES:
        return None
    content = (row.get("message") or {}).get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = " ".join(
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        )
    else:
        return None
    text = " ".join(re.sub(r"<[^>]+>", " ", text).split())
    if not text or AGENT_PREAMBLE.match(text):
        return None
    return text


def human_prompts(transcript):
    prompts = []
    with open(transcript, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
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
    from kingstack.secret_filter import keep_public
    return keep_public(prompts)


def upsert(runtime: Path, candidate: Candidate) -> None:
    from kingstack.secret_filter import inspect
    if inspect(candidate.text):
        return
    path = inbox_path(runtime)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    with os.fdopen(descriptor, "r+") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        try:
            inbox = Inbox.parse(handle.read())
            existing = inbox.find(candidate.session)
            if existing is not None and existing.reviewed:
                return
            if existing is not None:
                inbox.pending = [
                    candidate if item is existing else item for item in inbox.pending
                ]
            else:
                inbox.pending.append(candidate)
            handle.seek(0)
            handle.write(inbox.render())
            handle.truncate()
            os.chmod(path, 0o600)
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def log_error(runtime: Path, message: str) -> None:
    path = Path(runtime) / "memory-review.error.log"
    try:
        with open(path, "a", encoding="utf-8") as handle:
            handle.write("%s %s\n" % (datetime.now().isoformat(timespec="seconds"), message))
    except OSError:
        pass
