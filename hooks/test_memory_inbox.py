#!/usr/bin/env python3
"""Tests for the memory-review inbox grammar and the promote path.

    python3 ~/.claude/hooks/test_memory_inbox.py

Every case here is a bug that reached the live inbox once, or an invariant the
Stop hook depends on. The hook writes this file from every session, so a grammar
regression silently eats candidates.
"""
import json
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import memory_inbox as mi

LINE = (
    "- [ ] 2026-08-18 12:52 | plugins | goal | Build me a distiller | 1 prompt | "
    "e73e60d3 | /Users/mac/.claude/projects/-Users-mac-Desktop-Work-plugins/e73e60d3.jsonl\n"
)
PERSONAL = (
    "- [ ] 2026-08-18 13:34 | overclock | correction | fix this for long term | 96 prompts | "
    "4d77f484 | /Users/mac/.claude-personal/projects/-Users-mac-Desktop-Work-overclock/4d77f484.jsonl\n"
)

CASES = []


def case(fn):
    CASES.append(fn)
    return fn


@case
def line_round_trips():
    c = mi.Candidate.parse(LINE)
    assert c.session == "e73e60d3", c.session
    assert c.kind == "goal" and c.project == "plugins"
    assert c.prompts == 1 and not c.reviewed
    assert c.render() == LINE, c.render()


@case
def header_naming_the_marker_keeps_lines_pending():
    text = mi.HEADER + LINE + PERSONAL
    assert mi.REVIEWED_MARKER in mi.HEADER, "header must still name the section"
    inbox = mi.Inbox.parse(text)
    assert len(inbox.pending) == 2, "prose mention of the marker swallowed pending lines"
    assert not inbox.reviewed


@case
def reviewed_section_round_trips():
    inbox = mi.Inbox.parse(mi.HEADER + LINE + PERSONAL)
    inbox.mark_reviewed("e73e60d3", "promoted: project_x.md")
    again = mi.Inbox.parse(inbox.render())
    assert [c.session for c in again.pending] == ["4d77f484"]
    assert [c.session for c in again.reviewed] == ["e73e60d3"]
    assert again.reviewed[0].outcome == "promoted: project_x.md"


@case
def routing_follows_the_transcript_profile():
    assert ".claude/projects" in mi.Candidate.parse(LINE).routing()["memory_dir"]
    personal = mi.Candidate.parse(PERSONAL).routing()
    assert personal["memory_dir"].startswith(os.path.expanduser("~/.claude-personal"))
    assert personal["project_slug"] == "-Users-mac-Desktop-Work-overclock"
    stray = mi.Candidate.parse(LINE)
    stray.transcript = "/tmp/loose.jsonl"
    assert stray.routing()["memory_dir"] is None


@case
def upsert_refreshes_pending_and_spares_reviewed():
    with sandbox() as tmp:
        mi.REVIEW_FILE = os.path.join(tmp, "inbox.md")
        first = mi.Candidate.parse(LINE)
        mi.upsert(first)
        busier = mi.Candidate.parse(LINE)
        busier.prompts = 12
        mi.upsert(busier)
        inbox = mi.load()
        assert len(inbox.pending) == 1 and inbox.pending[0].prompts == 12

        mi.edit_inbox(lambda ib: ib.mark_reviewed("e73e60d3", "rejected: noise"))
        mi.upsert(mi.Candidate.parse(LINE))
        inbox = mi.load()
        assert not inbox.pending, "a reviewed session must never be re-offered"
        assert inbox.reviewed[0].outcome == "rejected: noise"


@case
def promote_writes_memory_and_index_idempotently():
    with sandbox() as tmp:
        mi.REVIEW_FILE = os.path.join(tmp, "inbox.md")
        bank = os.path.join(tmp, "bank")
        mi.upsert(mi.Candidate.parse(LINE))
        body = os.path.join(tmp, "body.md")
        with open(body, "w") as fh:
            fh.write("A fact. See [[other]].\n\n**Why:** it matters.\n")
        args = [
            "promote", "--session", "e73e60d3", "--name", "a-fact",
            "--type", "project", "--description", "One line",
            "--title", "a fact", "--body-file", body, "--memory-dir", bank,
        ]
        assert mi.main(args) == 0
        assert mi.main(args) == 0

        path = os.path.join(bank, "project_a_fact.md")
        text = open(path).read()
        assert text.startswith("---\nname: a-fact\n"), text[:40]
        assert "  type: project\n" in text and "originSessionId: e73e60d3" in text
        assert "**Why:**" in text

        index = open(os.path.join(bank, "MEMORY.md")).read()
        assert index.count("project_a_fact.md") == 1, "index line duplicated"
        assert index.startswith("# Memory Index")

        inbox = mi.load()
        assert not inbox.pending
        assert inbox.reviewed[0].outcome == "promoted: project_a_fact.md"


@case
def promote_refuses_malformed_input():
    with sandbox() as tmp:
        mi.REVIEW_FILE = os.path.join(tmp, "inbox.md")
        mi.upsert(mi.Candidate.parse(LINE))
        bank = os.path.join(tmp, "bank")
        good = os.path.join(tmp, "good.md")
        with open(good, "w") as fh:
            fh.write("Fact.\n\n**Why:** reason.\n\n**How to apply:** thus.\n")
        thin = os.path.join(tmp, "thin.md")
        with open(thin, "w") as fh:
            fh.write("Fact with no why.\n")

        def promote(**over):
            args = {
                "--session": "e73e60d3", "--name": "ok-name", "--type": "project",
                "--description": "One line", "--body-file": good,
                "--memory-dir": bank,
            }
            args.update(over)
            flat = ["promote"]
            for k, v in args.items():
                flat += [k, v]
            return mi.main(flat)

        assert promote(**{"--name": "Bad_Name"}) == 1, "accepted a non-kebab name"
        assert promote(**{"--body-file": thin}) == 1, "accepted a project without Why"
        assert promote(**{"--type": "feedback", "--body-file": thin}) == 1
        assert promote(**{"--session": "ffffffff"}) == 1, "accepted an unknown session"
        assert promote(**{"--description": "   "}) == 1, "accepted a blank description"
        assert not os.path.exists(bank), "a refused promote must write nothing"
        assert mi.load().pending, "a refused promote must leave the line pending"


@case
def agent_role_prompts_are_not_human_prompts():
    rows = [
        {"type": "user", "promptSource": "typed",
         "message": {"content": "lets fix this for long term"}},
        {"type": "user", "promptSource": "sdk",
         "message": {"content": "You are an expert code reviewer for this repo."}},
        {"type": "user", "promptSource": "sdk",
         "message": {"content": "Your job is to REFUTE each finding."}},
        {"type": "user", "promptSource": "typed", "isSidechain": True,
         "message": {"content": "subagent chatter"}},
        {"type": "user", "message": {"content": "tool result"}},
        {"type": "assistant", "promptSource": "typed",
         "message": {"content": "not a prompt"}},
    ]
    kept = [t for t in (mi.prompt_text(r) for r in rows) if t]
    assert kept == ["lets fix this for long term"], kept


@case
def human_prompts_reads_a_transcript():
    with sandbox() as tmp:
        path = os.path.join(tmp, "session.jsonl")
        with open(path, "w") as fh:
            fh.write(json.dumps({"type": "user", "promptSource": "typed",
                                 "message": {"content": "<command-name>/loop</command-name> keep going"}}) + "\n")
            fh.write("not json\n\n")
            fh.write(json.dumps({"type": "user", "promptSource": "typed",
                                 "message": {"content": [{"type": "text", "text": "second"}]}}) + "\n")
        assert mi.human_prompts(path) == ["/loop keep going", "second"]


class sandbox(object):
    def __enter__(self):
        self.saved = mi.REVIEW_FILE
        self.tmp = tempfile.mkdtemp(prefix="memory-inbox-test-")
        return self.tmp

    def __exit__(self, *exc):
        mi.REVIEW_FILE = self.saved
        shutil.rmtree(self.tmp, ignore_errors=True)


def run():
    failed = 0
    for fn in CASES:
        try:
            fn()
            print("ok    %s" % fn.__name__)
        except AssertionError as exc:
            failed += 1
            print("FAIL  %s: %s" % (fn.__name__, exc))
    print("\n%d passed, %d failed" % (len(CASES) - failed, failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(run())
