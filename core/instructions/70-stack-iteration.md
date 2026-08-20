
# Process framework: pstack

Lauren Tan's pstack (adapted from cursor/plugins, 2026-08-18) is the process
framework, in `~/.claude/skills/` for both profiles.

**Default-on.** For any non-trivial task (bug, feature, refactor, investigation,
migration, anything past a quick question or one-line edit), invoke `poteto-mode`
first unasked and let it pick the playbook and skills; never hand-sequence them.
Restate the goal as a checkable finish condition, deriving one if the request has
none. Skip only for trivial lookups, pure conversation, or when Hassan says to
work outside it.

Model roles live in `~/.claude/pstack-models.md`. The superpowers plugin is
disabled in favor of pstack. One front door.

**Absorbing pstack whole, kept current.** The install is a scripted port of the
upstream checkout at `~/Desktop/Work/plugins/pstack`, never a hand-edited fork.
`~/.claude/scripts/sync-pstack.sh` pulls upstream and re-applies every
Cursor-to-Claude adaptation; run it whenever Lauren ships (she commits every
1-2 days; last synced commit is in `~/.claude/pstack-upstream.txt`). Never edit
a pstack skill in place, the next sync overwrites it. Anything of mine goes in
`king-mode` (my layer, mined from my transcripts, refreshed with
`/automate-me update king-mode`) or in this file. Her guide is the manual:
`plugins/pstack/docs/guide/`, read it in order once.
Stack iteration is a standing thread, not a standing session: ideas and open items live
in `~/.claude/docs/BACKLOG.md` (tracked). When Hassan shares an idea for the stack in any
session, append it to the backlog's Ideas section (dated) so no session has to stay alive
to remember it. A "stack session" starts by reading the backlog.
`~/.claude/scripts/check-setup.sh` (alias `claude-check`) verifies the whole setup in
2 s: run it after any hook, skill, or profile change, or when a session behaves oddly.
`~/.claude/scripts/usage-report.py` (alias `claude-usage`, `--today`, `--days N`, `--by
model|project`) reports real token usage and estimated cost from the transcripts;
`~/.claude/usage.db` stopped recording in April 2026 and is not the source of truth.
A nightly launchd job (`com.hassan.claude-usage-snapshot`, 00:23) rolls each day into
`~/.claude/usage-ledger.csv` (permanent; transcripts expire in ~30 days) and rewrites
`~/.claude/usage-summary.md` (last 30 days, ctx/turn, by project, week-over-week trend).
