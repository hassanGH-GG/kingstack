# Cursor Agent adapter notes

Cross-agent compatibility: CLAUDE.md is the Claude adapter guidance filename.
Cursor Agent uses AGENTS.md. Shared policy may mention the old Claude home as
history.

Shared kingstack policy is in this file. Model names here are Cursor-native.
pstack skills stay in their Cursor-native form. Shared curated memory lives
under `~/.kingstack/memory` and is not Cursor native memory.
The canonical checkout is `~/Desktop/Work/kingstack`.
No live Cursor path is linked until Hassan approves the pre-link briefing.
Cursor has no native status-line hook. Run `kingstack status` or
`hooks/ctx-status.py` for the same cache-read cost math as Claude and Codex.
