---
name: memory-review
description: Distil the session-memory inbox into real memory files. Use for /memory-review, "review my memory inbox", "promote memory candidates", "what's waiting in memory review", or when ~/.claude/memory-review.md has pending lines.
---

# Memory review

The Stop hook (`~/.claude/hooks/session-memory-distiller.py`) parks one candidate
line per session in `~/.claude/memory-review.md`. This pass turns approved
candidates into memory files in the right project's memory bank and clears them
from the inbox. Hassan approves or rejects every candidate; never write a memory
file from a draft he has not seen.

**Every inbox and memory-bank write goes through the CLI.** Never hand-edit
`memory-review.md` or a `MEMORY.md`. Live sessions write that inbox from their
own Stop hooks, and the CLI is what holds the lock they share.

    CLI=~/.claude/hooks/memory_inbox.py

## 1. Read the inbox

    python3 $CLI list --json

Each candidate gives you `session` (the id every other command keys on), `kind`
(`correction` or `goal`), the truncated prompt, `prompts` (how long the session
ran), `transcript`, and the `memory_dir` derived from that path. The bank follows
the transcript, so a candidate captured under `~/.claude-personal` promotes into
that profile's bank, not the current session's.

No pending candidates means the pass is done. Say so and stop.

## 2. Draft one memory per candidate

The inbox text is a truncated prompt, not a fact. Read what actually happened:

    python3 $CLI show --session <id8>

Then draft, from the transcript and nothing else:

- **name** kebab-case slug, the memory's identity and its `[[link]]` target.
- **type** `user`, `feedback`, `project`, or `reference`. A correction Hassan gave
  about how to work is `feedback`. Ongoing work, goals, or constraints are
  `project`. Who he is or what he prefers is `user`. A URL, dashboard, or ticket
  pointer is `reference`.
- **description** one line, written so a future session can judge relevance from
  the index alone.
- **body** the fact itself. `feedback` and `project` need a `**Why:**` line;
  `feedback` also needs `**How to apply:**`. Link related memories with
  `[[their-name]]`, including ones not written yet.

Reject rather than draft when the candidate is a bare session goal already
visible in the repo or git history, a one-prompt session with no durable fact, or
an agent-to-agent prompt that slipped through capture. A short session that ended
in a real correction is still worth promoting; prompt count is not the signal.

Check `memory_dir` for a file that already covers the fact. Update it by
promoting with the **same `--name`** rather than adding a near-duplicate.

## 3. Get a verdict on each one

Cluster candidates of one class into a single question (four leaked reviewer
prompts from one repo are one decision, not four). Otherwise ask per candidate,
at most four questions per `AskUserQuestion` call, options `Promote`, `Reject`,
`Skip for now`. Put the drafted name, type, and description in the option text so
the approval is informed. Lead with your recommendation.

## 4. Apply the verdicts

Write the body to a scratchpad file first, then:

    python3 $CLI promote --session <id8> --name <slug> --type <type> \
      --description "<one line>" --title "<index link text>" --body-file <path>

    python3 $CLI reject --session <id8> [--session <id8> ...] --reason "<why>"

`promote` writes `<type>_<snake_name>.md`, upserts the `MEMORY.md` pointer, and
moves the inbox line into the `## Reviewed` section with a ticked box. The tick is
what stops the hook re-offering a session that is still open, so a reviewed line
stays in the file by design. Both commands are idempotent; re-running one
converges instead of duplicating. `Skip for now` means run no command.

## 5. Report

One table: candidate, verdict, memory file. Then the paths written and how many
candidates remain pending. If a promotion was really an update to an existing
memory, say which file it changed.
