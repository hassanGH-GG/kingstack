---
name: handoff-to-codex
description: >-
  Write a packet so Codex can continue the same job. Use when handing work
  to Codex, "handoff to Codex", or "write a Codex brief".
---

# Handoff to Codex

Write a packet with the CLI. Do not invent a host spawn or a loop primitive
on Codex. Those do not exist there.

    kingstack handoff --finish "<exact done means>" --out HANDOFF.md

The packet names the finish condition, dirty paths, commit state, headroom
ids, and memory names to recall. Codex opens `HANDOFF.md` and continues
from that file. The same job is a row in `~/.kingstack/sessions`. Continue
later with `kingstack session continue <id>`.

If headroom ids are listed, retrieve with `kingstack headroom retrieve <id>`
only when a stack frame or name is missing. Do not paste the raw blob back
into the thread.

Recall a memory body with `kingstack memory recall <name>` when the index
name matches the finish condition.
