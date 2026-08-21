
# Process framework: pstack

Lauren Tan's pstack (adapted from cursor/plugins) is the process framework.
Bundled skills come from the kingstack catalog, not from editing
`~/.claude/skills/` by hand.

**Default-on.** For any non-trivial task (bug, feature, refactor, investigation,
migration, anything past a quick question or one-line edit), invoke `poteto-mode`
first unasked and let it pick the playbook and skills; never hand-sequence them.
Restate the goal as a checkable finish condition, deriving one if the request has
none. Skip only for trivial lookups, pure conversation, or when Hassan says to
work outside it.

Model roles live in `~/Desktop/Work/kingstack/pstack-models.md`. Superpowers
is disabled. One front door is pstack.

**Absorbing pstack whole, kept current.** The install is a scripted port of the
upstream checkout at `~/Desktop/Work/plugins/pstack`, never a hand-edited fork.
`~/Desktop/Work/kingstack/scripts/sync-pstack.sh` pulls upstream and re-applies
every adapter transform; run it whenever Lauren ships. Last synced commit is in
`~/Desktop/Work/kingstack/pstack-upstream.txt`. Never edit a pstack skill in
place; the next sync overwrites it. Anything of Hassan's goes in `king-mode`
or in this file. Her guide is the manual: `plugins/pstack/docs/guide/`.
Stack iteration is a standing thread: ideas live in
`~/Desktop/Work/kingstack/docs/ROADMAP.md`. When Hassan shares an idea for the
stack in any session, append it to Ideas (dated). A "stack session" starts by
reading that file.
`~/Desktop/Work/kingstack/scripts/kingstack setup` prepares `~/.kingstack`
and never writes a native home. `~/Desktop/Work/kingstack/scripts/kingstack check --all --mode staged` verifies
the checkout. Live health stays unhealthy until a native home is linked.
`~/Desktop/Work/kingstack/scripts/kingstack effort --file` scans spawn lines.
`~/Desktop/Work/kingstack/scripts/kingstack handoff --finish` writes a Codex
packet. `~/Desktop/Work/kingstack/scripts/kingstack session list` shows the
working-set index. CI runs unit tests and staged health.
`~/Desktop/Work/kingstack/scripts/usage-report.py` reports token usage from
transcripts. A nightly launchd job (`com.hassan.claude-usage-snapshot`, 00:23)
rolls each day into the usage ledger. Transcripts expire in about 30 days.
