# kingstack

Hassan Ghandour's operating system for Claude Code: Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack) absorbed whole as the process engine, with a personal layer, persistent memory, cost routing, and the mechanisms that make all of it fire on every session, unprompted, across two subscriptions.

This repository *is* `~/.claude`. It tracks only what is authored here (an allowlist `.gitignore`); everything generated, cached, or secret stays untracked.

## Why kingstack, if pstack exists

pstack answers one question extremely well: how should rigorous agent work run? kingstack does not compete with that; pstack *is* its engine, absorbed whole and kept current from upstream. kingstack answers everything around that question that a plugin structurally cannot: how the work starts, what it remembers, what it costs, how it stays current, and how it fits one specific person.

The thesis in one line: **pstack tells the agent what to do; kingstack makes it happen and checks that it did.**

| pstack, by design a plugin | kingstack adds |
|---|---|
| Opt-in. You type `/poteto-mode` or nothing happens. | Ignition. A SessionStart hook injects the contract into every session, both profiles. Verified to fire on a bare prompt with no slash command. |
| No memory. Every session starts as a stranger; `recall` and `reflect` are helpers, not a store. | Persistent, gated memory. A Stop hook captures a candidate every turn, `/memory-review` promotes what the human approves into per-project banks with provenance, an index, and tests. |
| Generic. The same behavior for every user. | A personal layer mined from evidence. `king-mode` was distilled from about 1,000 real prompts, is refreshed biweekly, and is kept apart from the engine so neither clobbers the other. |
| A model table. Roles map to models, statically. | A cost policy that runs. Every subagent is routed by class of work, cheapest tier first; polling is never an LLM turn; bulk never enters the main thread; a nightly ledger survives transcript expiry and shows context-per-turn week over week. |
| The port is maintained by hand. | Scripted absorption. `sync-pstack.sh` pulls upstream, re-applies every Cursor-to-Claude adaptation, installs pstack's declared cross-plugin dependencies, and refuses to finish if any Cursor-ism survives. Upstream keeps flowing; the personal layer never breaks. |
| Prose the model reads. | Mechanisms that verify. An 18-check health script, a test suite for the memory pipeline, launchd schedules, and an allowlisted git history of the framework itself. |

What a person gains, in practice: the same rigor pstack promises, but on every session without remembering to ask for it; an agent that starts each session already knowing the project; a working style encoded from how they actually work rather than how they describe it; and a token bill that is routed and measured instead of inherited. Fork it, run `/automate-me` for your own `-mode`, and the engine plus mechanisms are yours; only `king-mode` and the identity section of `CLAUDE.md` are specific to me.

## The layers

| Layer | Answers | Lives in | Changed by |
|---|---|---|---|
| Identity and standing rules | who am I, what always holds | `CLAUDE.md` | hand |
| Process | how rigorous work runs | pstack (43 skills, 23 playbooks, 2 agents) + 3 team-kit deps + 5 adopted extras | `scripts/sync-pstack.sh` from upstream; **never hand-edited** |
| Taste | how it should feel to me | `skills/king-mode/` | `/automate-me update king-mode`, biweekly via launchd |
| Memory | what persists across sessions | `hooks/session-memory-distiller.py` → `memory-review.md` inbox → `skills/memory-review/` → per-project banks | every turn (capture), me (approve) |
| Cost | how tokens get spent | `model-routing.md`, `pstack-models.md`, `scripts/usage-*.py` | ruler per subagent; nightly ledger |
| Ignition | how it all fires | `hooks/session-start-poteto.sh` (SessionStart) | hook |
| Health | is it still wired | `scripts/check-setup.sh` | run after any change |

## What happens when a session starts

1. `CLAUDE.md` loads: identity, team, standing rule, engineering discipline, git safety, routing policy.
2. The SessionStart hook injects the contract: invoke `poteto-mode` then `king-mode` for any non-trivial task; restate the goal as a checkable finish condition; route subagents by class of work; polling is never an LLM turn; bulk never enters the main thread. If memory candidates are waiting, it says so once.
3. Every turn end, the Stop hook distills a candidate memory line into the inbox. `/memory-review` promotes what I approve into the right project's memory bank.

Both profiles (`claude`, `claude-personal`) read this same tree through symlinks; only the login differs.

## Commands

| Command | Does |
|---|---|
| `claude-check` (`scripts/check-setup.sh`) | 16 checks in 2 s: symlinks, hooks, contract emission, skills, pstack sync stamp, Cursor-ism leak, memory tests, launchd jobs, ledger freshness. Exit 1 on drift. |
| `scripts/sync-pstack.sh` | `git pull` the cursor/plugins checkout, mirror pstack + deps + extras into `skills/`, reapply every Cursor→Claude adaptation, refuse to finish if any survive. Idempotent. |
| `claude-usage` (`scripts/usage-report.py`) | token usage and estimated cost from transcripts: `--today`, `--days N`, `--by model\|project`. |
| `scripts/usage-snapshot.py` | nightly rollup into `usage-ledger.csv` (permanent; transcripts expire in ~30 days) and `usage-summary.md`. |
| `scripts/refresh-king-mode.sh` | biweekly `/automate-me update king-mode` over recent transcripts; backs up, rolls back if malformed. |
| `bun scripts/measure.ts check ...` | rerun a subagent's quantitative claims on its real branch; flag drift. |
| `scripts/install-launchd.sh` | (re)load the two schedules from `launchd/`. |
| `/memory-review` | promote or reject inbox candidates. |

## Rules that keep it alive

- **Never hand-edit a pstack skill.** The next sync overwrites it. Anything of mine goes in `king-mode` or `CLAUDE.md`.
- **Every correction is a design defect.** Eliminate it structurally, else a test, else a rule; human review is the floor.
- **One home per fact.** Facts in memory, identity in `CLAUDE.md`, process in pstack, taste in king-mode. Nothing lives twice.
- **Cheapest tier that can succeed.** Main thread Fable at effort medium, set once; everything below routed by `model-routing.md`, escalated on evidence.
- **Run `claude-check` after touching anything here.**

## Fresh machine

```bash
git clone https://github.com/hassanGH-GG/kingstack ~/.claude
git clone https://github.com/cursor/plugins ~/Desktop/Work/plugins   # pstack source
~/.claude/scripts/sync-pstack.sh --no-pull                             # generate the 51 skills
~/.claude/scripts/install-launchd.sh
python3 ~/.claude/hooks/test_memory_inbox.py && ~/.claude/scripts/check-setup.sh
```
Then `/model` Fable, `/effort` medium, and for a second profile symlink `CLAUDE.md skills agents settings.json projects plugins history.jsonl` into its config dir.

## Codex

Claude Code is the primary agent. Codex is used as an executor for well-specified work: Claude writes the brief, Codex runs it in waves, Claude verifies the result. The `codex` plugin (rescue subagent, optional stop-time review gate) is installed; kingstack adds no Codex-specific machinery yet, and this section says so rather than implying otherwise.

What kingstack already governs about that loop: the routing ruler forbids spending LLM turns on polling, so "watch the Codex run" is a Monitor or a hook that wakes the session on change, not a Claude turn every five minutes; and `king-mode` writes hand-off briefs so the receiving agent reviews and improves rather than copies. On the roadmap, if Codex stays in the loop: a `handoff-to-codex` skill (brief template, wave structure, verify gate per wave) and a watcher that observes Codex's branch or session and wakes Claude when a wave lands.

## Provenance

pstack is Lauren Tan's, MIT, vendored via script from `cursor/plugins` (last synced commit in `pstack-upstream.txt`). `deslop`, `control-cli`, `control-ui`, `verify-this`, `make-pr-easy-to-review` are from `cursor-team-kit`; the two `thermo-nuclear-*` rubrics from `thermos`; `cli-for-agents` from `cli-for-agent`; `measure.ts` is a compacted port of `orchestrate/measurements.ts`. All MIT, all Cursor 2026. Everything else here is mine.
