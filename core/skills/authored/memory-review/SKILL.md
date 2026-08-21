---
name: memory-review
description: Distil the shared memory inbox into real memory files. Use for /memory-review, "review my memory inbox", "promote memory candidates", or "what's waiting in memory review".
---

# Memory review

The portable Stop hook parks one candidate per session in
`~/.kingstack/memory`. This pass turns approved candidates into memory files
in the right project's bank. Hassan approves or rejects every candidate;
never write a memory file from a draft he has not seen.

**Every inbox and memory-bank write goes through the CLI.** Never hand-edit
`inbox.jsonl` or a `MEMORY.md`.

    kingstack memory list
    kingstack memory harvest --inbox <memory-review.md>
    kingstack memory consolidate

`harvest` turns inbox corrections into candidates. `consolidate` proposes
merges for near-duplicate promoted files. Both write candidates only.
Hassan still promotes or rejects.

## 1. Read the inbox

    kingstack memory list

Each candidate gives you `session` (the id every other command keys on), `kind`
(`correction` or `goal`), the truncated prompt, `prompts` (how long the session
ran), `transcript`, and the `memory_dir` derived from that path. The bank follows
the project identity, so a candidate promotes into the shared bank for that
project, not a host-specific tree.

No pending candidates means the pass is done. Say so and stop.

## 2. Draft one memory per candidate

The inbox text is a truncated prompt, not a fact. Read what actually happened:

    kingstack memory show c_<id>

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
an agent-to-agent prompt that slipped through capture. Stop already drops
one-prompt health probes. If one still lands, reject it. A short session that ended
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

    kingstack memory promote c_<id> --name <slug> --type <type> \
      --description "<one line>" --body "<fact>"

    kingstack memory reject c_<id> --reason "<why>"

`promote` writes `<type>_<snake_name>.md`, upserts the `MEMORY.md` pointer, and
moves the inbox line into the `## Reviewed` section with a ticked box. The tick is
what stops the hook re-offering a session that is still open, so a reviewed line
stays in the file by design. Both commands are idempotent; re-running one
converges instead of duplicating. `Skip for now` means run no command.

## 5. Report

One table: candidate, verdict, memory file. Then the paths written and how many
candidates remain pending. If a promotion was really an update to an existing
memory, say which file it changed.
