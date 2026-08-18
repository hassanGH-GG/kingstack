# kingstack

Hassan Ghandour's operating system for Claude Code: Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack) absorbed whole as the process engine, with a personal layer, persistent memory, cost routing, and the mechanisms that make all of it fire on every session, unprompted, across two subscriptions.

This repository *is* `~/.claude`. It tracks only what is authored here (an allowlist `.gitignore`); everything generated, cached, or secret stays untracked.

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

## Provenance

pstack is Lauren Tan's, MIT, vendored via script from `cursor/plugins` (last synced commit in `pstack-upstream.txt`). `deslop`, `control-cli`, `control-ui`, `verify-this`, `make-pr-easy-to-review` are from `cursor-team-kit`; the two `thermo-nuclear-*` rubrics from `thermos`; `cli-for-agents` from `cli-for-agent`; `measure.ts` is a compacted port of `orchestrate/measurements.ts`. All MIT, all Cursor 2026. Everything else here is mine.
