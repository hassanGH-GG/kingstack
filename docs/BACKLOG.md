# kingstack backlog

The standing thread for improving the stack. Hassan drops ideas here (or says them in any
session, which appends here); a stack session picks one up, does it, moves it to Done with
the commit hash. The backlog is the session; any chat is just a window onto it.

Ritual: `cd ~/.claude && claude`, then "stack session". The agent reads this file and the
`-Users-mac` memory bank, proposes the top item or takes a new idea, and works it with a
finish condition. One item per sitting beats five half-done.

## Ideas (Hassan's, undecided)

- (drop new ideas here, one line each, date them)

## Ready (decided, not started)

- **Memory upgrade: re-open on session growth.** A session reviewed at turn 10 is suppressed
  forever; a correction at turn 40 is lost. Store prompt-count at review time, re-offer when
  it grows. From the continual-learning audit, 2026-08-18.
- **Memory upgrade: consolidation pass.** `memory_inbox.py gc`: propose merges of
  near-duplicate memories per bank, soft cap per type. Same audit.
- **Correction harvester (self-improvement loop 1).** Nightly: detect correction-shaped
  turns, classify fact/preference/process, auto-promote the unambiguous ones with
  provenance; git commit is the safety net. Designed 2026-08-18, not built.
- **`handoff-to-codex` skill.** Brief template, wave structure, verify gate per wave, plus a
  watcher that wakes Claude when a wave lands. Only if Codex stays in the loop.

## Waiting on something

- **Flip fable pins back** in `pstack-models.md` and delete its Availability section, when
  Fable credits reset. The file says so itself.
- **beam to-host proof.** Needs Remote Login on (System Settings, ten seconds) or any ssh
  host. Code written 2026-08-18, local path proven, remote path not.
- **Host decision.** Justified only by: runs surviving sleep, work on local uncommitted
  state, or the team Slack door. Re-decide after a week of Remote Control use.
- **king-mode judgment areas.** The first draft skews to steering (status, approvals);
  design taste and architecture thinking are under-mined. Revisit at the Sept 1 refresh
  with real work in the window, not framework-building.

## Review dates

- **Sept 1:** first live king-mode refresh fires. Read the changelog and the diff.
- **~Sept 1:** two weeks of ledger data. Read `usage-summary.md` ctx/turn trend and
  `rework-report.py --days 14` against the 0.4 baseline. This answers "was it worth it".
- **Weekly-ish:** `sync-pstack.sh` (Lauren ships every 1-2 days), `claude-check`.

## Done

- 2026-08-18/19: everything in the repo history up to "handle a model tier running out of
  credits as a class". See `git log` rather than duplicating it here.

## Team track (separate decision, not personal)

- sadiestack proposal written (`docs/sadiestack-proposal.html`, artifact published).
  Waiting on: sending it to Ali/Michael, or dropping the team angle entirely.
