# Codex adapter notes

Cross-agent compatibility: CLAUDE.md is the Claude adapter guidance filename.
Codex uses AGENTS.md. Shared policy may mention the old Claude home as history.

Shared kingstack policy is in this file. Model names here are Codex-native.
Shared curated memory lives under `~/.kingstack/memory` and is not Codex
native memory. Recall with `kingstack memory recall`.
The canonical checkout is `~/Desktop/Work/kingstack`. Set `KINGSTACK_ROOT`
if the clone lives elsewhere. No live Codex path is linked until Hassan
approves the pre-link briefing.
Codex footer fields are the native `tui.status_line`. `kingstack status` also
prints model, effort, context, and subagent models. `kingstack effort --file`
scans spawn lines. `kingstack session list` shows the working-set index.
`kingstack handoff --finish` writes the packet this
adapter opens. Do not invent a host spawn or a loop primitive.
