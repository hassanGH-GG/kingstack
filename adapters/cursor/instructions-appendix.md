# Cursor adapter notes

Shared kingstack policy is in `~/.cursor/rules/kingstack/`. Those files are
the OS, not a home-root AGENTS.md. Project AGENTS.md still belongs to the
repo you have open.

Model names here are Cursor-native. pstack skills stay in their
Cursor-native form under `~/.cursor/skills/`. Shared curated memory lives
under `~/.kingstack/memory` and is not Cursor native memory.
The checkout is `~/Desktop/Work/kingstack`. Set `KINGSTACK_ROOT` if the
clone lives elsewhere. No live Cursor path is linked until Hassan
approves the pre-link briefing.
Cursor has no native status-line hook. Run `kingstack status` or
`hooks/ctx-status.py` for model, effort, context, and subagent models.
`kingstack effort --file` scans spawn lines. Inherit is fail.
`kingstack session list` shows the working-set index.
`skills-cursor`, `chats`, and `cli-config.json` stay Cursor's.
