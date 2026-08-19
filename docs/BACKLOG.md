# kingstack backlog

The standing thread for improving the stack. Hassan drops ideas here (or says them in any
session, which appends here); a stack session picks one up, does it, moves it to Done with
the commit hash. The backlog is the session; any chat is just a window onto it.

Ritual: `cd ~/.claude && claude`, then "stack session". The agent reads this file and the
`-Users-mac` memory bank, proposes the top item or takes a new idea, and works it with a
finish condition. One item per sitting beats five half-done.

## Ideas (Hassan's, undecided)

- 2026-08-19 **Colleague-ready.** A teammate should be able to adopt the stack (fork kingstack, run /automate-me for their own -mode). Overlaps the team track below; the personal-vs-shared split already exists, what is missing is a tested fork path.
- 2026-08-19 **Effort control, verified not assumed.** Medium default and the ruler exist; nothing yet PROVES effort is set per spawn. Partly answered by the SubagentStart visibility hook (built 2026-08-19); a periodic audit of spawn calls in transcripts would close it.
- 2026-08-19 **Use /loop more.** Polling and recurring checks should default to /loop or Monitor, never manual turns. Candidate king-mode rule at the Sept 1 refresh; the evidence for it is in the overclock ledgers.
- 2026-08-19 **Usage-aware agent.** DONE same day: SessionStart now injects yesterday's ctx/turn and cost, and a daily usage-watch sweep raises ATTENTION when the trend is bad.
- 2026-08-19 **Cloud-capable, not laptop-bound.** Cloud sessions and routines should be able to run with the stack. kingstack is already a clonable repo with a bootstrap; untested in a cloud env. Test: one cloud routine that clones kingstack and passes claude-check.
- 2026-08-19 **Not married to Claude.** Audit what is Claude-specific (hooks format, Agent tool, skill frontmatter) vs portable (scripts, ledgers, memory files, backlog, pstack content, which began as Cursor files). Deliverable: a PORTABILITY.md naming the seams and an AGENTS.md mirror so another harness can read the same brain.
- 2026-08-19 **Grok-bot-level on Slack.** The minions gateway hardened is exactly this (thread=session, team-visible). Needs the host + the injection fixes named in docs/sadiestack-proposal.html. Team track, not personal.
- 2026-08-19 **Subagent visibility, enforced.** Every spawn reports model+effort to the parent. DONE same day via a SubagentStart hook; "inherit" is flagged so a lazy spawn is visible.

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

- **Aug 26:** one week of post-enforcement ledger data. Test the four predictions in
  `docs/token-projection-2026-08.md` (no day >250k ctx/turn; 7-day average in 120-180k;
  cost per turn falls proportionally; no weight-attributable credit death). Verdict via
  the verify-this protocol: VERIFIED / NOT VERIFIED / INCONCLUSIVE, against the ledger.

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
