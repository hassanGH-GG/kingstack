# Codex adapter notes

Cross-agent compatibility: CLAUDE.md is the Claude adapter guidance filename.
Codex uses AGENTS.md. Shared policy may mention the old Claude home as history.

Shared kingstack policy is in this file. Model names here are Codex-native.
Shared curated memory lives under `~/.kingstack/memory` and is not Codex
native memory. Recall with `kingstack memory recall`.
The canonical checkout is `~/Desktop/Work/kingstack`.
No live Codex path is linked until Hassan approves the pre-link briefing.
Codex footer fields are the native `tui.status_line`. The same cache-read cost
math is `kingstack status` or `hooks/ctx-status.py`.
