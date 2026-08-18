# kingstack

Hassan Ghandour's operating system for Claude Code: Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack) absorbed whole as the process engine, with a personal layer, persistent memory, cost routing, and the mechanisms that make all of it fire on every session, unprompted, across two subscriptions.

This repository *is* `~/.claude`. It tracks only what is authored here, through an allowlist `.gitignore`; everything generated, cached, or secret stays untracked by construction.

## Why kingstack, if pstack exists

pstack answers one question extremely well: how should rigorous agent work run? kingstack does not compete with that. pstack *is* its engine, absorbed whole and kept current from upstream. kingstack answers everything around that question that a plugin structurally cannot: how the work starts, what it remembers, what it costs, how it stays current, and how it fits one specific person.

The thesis in one line: **pstack tells the agent what to do; kingstack makes it happen and checks that it did.**

| pstack, by design a plugin | kingstack adds |
|---|---|
| Opt-in. You type `/poteto-mode` or nothing happens. | Ignition. A SessionStart hook injects the contract into every session, both profiles. Verified to fire on a bare prompt with no slash command. |
| No memory. Every session starts as a stranger; `recall` and `reflect` are helpers, not a store. | Persistent, gated memory. A Stop hook captures a candidate every turn; `/memory-review` promotes what the human approves into per-project banks with provenance, an index, and tests. |
| Generic. The same behavior for every user. | A personal layer mined from evidence. `king-mode` was distilled from about 1,000 real prompts, is refreshed biweekly, and is kept apart from the engine so neither clobbers the other. |
| A model table. Roles map to models, statically. | A cost policy that runs. Every subagent is routed by class of work, cheapest tier first; polling is never an LLM turn; bulk never enters the main thread; two nightly ledgers survive transcript expiry. |
| The port is maintained by hand. | Scripted absorption. `sync-pstack.sh` pulls upstream, re-applies every Cursor-to-Claude adaptation, installs pstack's declared cross-plugin dependencies, refuses to overwrite anything hand-edited, and refuses to finish if a Cursor-ism survives. |
| Prose the model reads. | Mechanisms that verify. A 22-check health script, a test suite for the memory pipeline, three launchd schedules, and a git history of the framework itself. |

What a person gains, in practice: the same rigor pstack promises, but on every session without remembering to ask for it; an agent that starts each session already knowing the project; a working style encoded from how they actually work rather than how they describe it; and a token bill that is routed and measured instead of inherited. Fork it, run `/automate-me` for your own `-mode`, and the engine plus mechanisms are yours. Only `king-mode` and the identity section of `CLAUDE.md` are specific to me.

## The layers

| Layer | Answers | Lives in | Changed by |
|---|---|---|---|
| Identity and standing rules | who am I, what always holds | `CLAUDE.md` | hand |
| Process | how rigorous work runs | pstack (43 skills, 23 playbooks, 2 agents) plus 3 team-kit dependencies and 5 adopted extras | `scripts/sync-pstack.sh` from upstream; **never hand-edited** |
| Taste | how it should feel to me | `skills/king-mode/` | `/automate-me update king-mode`, biweekly via launchd |
| Memory | what persists across sessions | `hooks/session-memory-distiller.py` writes `memory-review.md`; `skills/memory-review/` promotes into per-project banks | every turn to capture, me to approve |
| Cost | how tokens get spent | `model-routing.md`, `pstack-models.md`, `scripts/usage-*.py` | the ruler per subagent; nightly ledger |
| Evidence | is any of this working | `usage-ledger.csv`, `rework-ledger.csv`, `usage-summary.md` | `scripts/nightly.sh` |
| Ignition | how it all fires | `hooks/session-start-poteto.sh` | SessionStart hook |
| Health | is it still wired | `scripts/check-setup.sh` | run after any change |

## What happens when a session starts

1. `CLAUDE.md` loads: identity, team, the standing rule, engineering discipline, git safety, routing policy.
2. The SessionStart hook injects the contract: invoke `poteto-mode` then `king-mode` for any non-trivial task; restate the goal as a checkable finish condition; route subagents by class of work; polling is never an LLM turn; bulk never enters the main thread. If memory candidates are waiting it says so once.
3. At every turn end the Stop hook distills a candidate memory line into the inbox. `/memory-review` promotes what I approve into the right project's bank.

Both profiles, `claude` and `claude-personal`, read this same tree through symlinks. Only the login differs.

## Repository map

```
CLAUDE.md              identity, standing rule, team, discipline, git safety, routing policy
model-routing.md       the cost ruler: classify each unit of work, cheapest tier that can succeed
pstack-models.md       pstack's own per-role model defaults; defers to the ruler for everything else
pstack-upstream.txt    last synced upstream commit, then every skill the sync installed
hooks/
  session-start-poteto.sh    SessionStart: emits the contract, plus the memory-inbox nudge
  poteto-mode-context.md     the contract text, edited here rather than in the script
  session-memory-distiller.py  Stop: appends one candidate per session to the inbox
  memory_inbox.py            the inbox format and CLI: list, show, promote, reject
  test_memory_inbox.py       9 cases; run after touching either memory file
scripts/
  check-setup.sh       claude-check: 22 checks, exit 1 on drift
  sync-pstack.sh       upstream to installed, with adaptations and the clobber guard
  refresh-king-mode.sh biweekly personal-layer refresh, with backup and rollback
  usage-report.py      claude-usage: tokens and cost, ad hoc
  usage-snapshot.py    nightly usage rollup into the permanent ledger and summary
  rework-report.py     how often the agent needs correcting, with an auditable sample list
  nightly.sh           runs both rollups; the target of the nightly launchd job
  run-sweeps.sh        runs each enabled sweep in its own headless session
  beam.sh              move a live session to another directory or machine and resume it
  box-task.sh          fire-and-forget unattended runs; an exit file is the completion truth
  measure.ts           rerun a subagent's quantitative claims on its real branch
  install-launchd.sh   load the schedules from launchd/, and name any stray job
skills/king-mode/      my layer: reply shape, autonomy, finish line, review lenses, voice
skills/memory-review/  the promote-or-reject pass over the inbox
sweeps/                one markdown file per unattended check; frontmatter is machine-read
launchd/               the three schedules, tracked so only known jobs get loaded
docs/                  proposals and design notes
```

Everything else under `~/.claude` (the other 63 skills, `projects/`, transcripts, caches, credentials, both ledgers) is generated or private, and untracked on purpose.

## Commands

| Command | Does |
|---|---|
| `claude-check` (`scripts/check-setup.sh`) | 22 checks in about two seconds: profile symlinks, both hooks, contract emission, the routing ruler, effort setting, critical skills, hand-edited skills, agents, pstack sync stamp, Cursor-ism leak, memory tests, three launchd jobs, both ledgers, repo hygiene. Exit 1 on drift. |
| `scripts/sync-pstack.sh` | Pull the cursor/plugins checkout, mirror pstack plus dependencies plus extras into `skills/`, reapply every Cursor-to-Claude adaptation, skip anything hand-edited, refuse to finish if a Cursor-ism survives. Idempotent. `--no-pull`, `--force`. |
| `claude-usage` (`scripts/usage-report.py`) | Tokens and estimated cost from transcripts: `--today`, `--days N`, `--by model\|project`. |
| `scripts/rework-report.py` | Correction-shaped prompts per 10 typed, by week or project. `--samples` to audit what matched, `--snapshot` to write the ledger. |
| `scripts/nightly.sh` | Both rollups; runs at 00:23 via launchd. |
| `scripts/refresh-king-mode.sh` | Biweekly `/automate-me update king-mode` over recent transcripts; backs up first, rolls back a malformed result. |
| `scripts/run-sweeps.sh` | Every enabled sweep in `sweeps/`, one isolated headless session each, scoped permissions, never `bypassPermissions`. `--only`, `--dry-run`. |
| `scripts/beam.sh` | Move a live session elsewhere and resume it with memory intact; the transcript is the transfer. `list`, `to-dir`, `to-host`, `fetch`. |
| `echo "brief" \| scripts/box-task.sh run <name>` | Fire-and-forget an unattended run; completion is an exit file, never process presence. `status`, `wait`, `result`, `list`. |
| `bun scripts/measure.ts check ...` | Rerun a subagent's quantitative claims on its real branch and flag drift. |
| `scripts/install-launchd.sh` | Load the three schedules from `launchd/` and name any stray `com.hassan.*` job that the repo does not track. |
| `/memory-review` | Promote or reject inbox candidates. |

## Schedules

| When | Job | Does |
|---|---|---|
| 00:23 daily | `com.hassan.claude-usage-snapshot` | `nightly.sh`: usage and rework rollups into the permanent ledgers |
| 07:41 daily | `com.hassan.kingstack-sweeps` | every enabled sweep, one headless session each |
| 07:17 on the 1st and 15th | `com.hassan.king-mode-refresh` | re-mine recent transcripts and revise `king-mode` |

## Knowing whether it works

Two numbers, both recorded nightly so they outlive the 30-day transcript window.

- **Context per turn**, in `usage-summary.md`. Almost all spend is context re-read, so this is the cost lever. It was averaging about 420k in August. Lower is both cheaper and sharper.
- **Rework rate**, from `rework-report.py`: how many of every 10 typed prompts are correction-shaped. The baseline over the 60 days before the framework existed was 0.4. It is a proxy rather than truth, which is why `--samples` exists; audit it whenever a number looks wrong.

## Rules that keep it alive

- **Never hand-edit a pstack skill.** The sync refuses to overwrite one and exits 3, but the file then drifts from upstream forever. `claude-check` reports hand edits and `sync-pstack.sh --force` discards them. Anything of mine goes in `king-mode` or `CLAUDE.md`.
- **Every correction is a design defect.** Eliminate it structurally, else a test, else a rule. Human review is the floor, not a plan.
- **One home per fact.** Facts in memory, identity in `CLAUDE.md`, process in pstack, taste in `king-mode`. Nothing lives twice.
- **Cheapest tier that can succeed.** Main thread on Fable or Opus at effort medium, set once by hand; everything below it routed by `model-routing.md` and escalated only on evidence.
- **Run `claude-check` after touching anything here**, and commit what it flags.

## Fresh machine

```bash
git clone https://github.com/hassanGH-GG/kingstack ~/.claude
git clone https://github.com/cursor/plugins ~/Desktop/Work/plugins   # the pstack source
~/.claude/scripts/sync-pstack.sh --no-pull        # generates the 51 skills and the manifest
~/.claude/scripts/install-launchd.sh              # loads the three schedules
python3 ~/.claude/hooks/test_memory_inbox.py      # 9 cases
~/.claude/scripts/rework-report.py --snapshot     # seeds the rework ledger
~/.claude/scripts/check-setup.sh                  # expect SETUP HEALTHY
```

Then set `/model` to Fable or Opus and `/effort` to medium. For a second profile, symlink `CLAUDE.md skills agents settings.json projects plugins history.jsonl` from its config directory into this one, so both logins share one brain.

## Codex

Claude Code is the primary agent. Codex is used as an executor for well-specified work: Claude writes the brief, Codex runs it in waves, Claude verifies the result. The `codex` plugin is installed, and kingstack adds no Codex-specific machinery yet; this section says so rather than implying otherwise.

What kingstack already governs about that loop: the routing ruler forbids spending LLM turns on polling, so watching a Codex run is a Monitor or a hook that wakes the session on change rather than a Claude turn every five minutes, and `king-mode` writes hand-off briefs so the receiving agent reviews and improves rather than copies. If Codex stays in the loop, the roadmap is a `handoff-to-codex` skill with a brief template and a verify gate per wave, plus a watcher on Codex's branch.

## Provenance

pstack is Lauren Tan's, MIT, vendored by script from `cursor/plugins`; the last synced commit is the first line of `pstack-upstream.txt`. `deslop`, `control-cli`, `control-ui`, `verify-this` and `make-pr-easy-to-review` come from `cursor-team-kit`, the two `thermo-nuclear-*` rubrics from `thermos`, and `cli-for-agents` from `cli-for-agent`. `measure.ts` is a compacted port of `orchestrate/measurements.ts`; the clobber guard, the sweeps registry and the tracked-only schedule install are ports of ideas from `heysadie/minions`. All MIT, all Cursor 2026 except minions. Everything else here is mine.
