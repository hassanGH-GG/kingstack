# Pre-link briefing

Status: WAITING FOR HASSAN

This document is the Phase F stop. Nothing under `~/.claude`, `~/.codex`, or
`~/.cursor` has been linked or replaced.

## What is ready

- Claude, Codex, and Cursor bundles render as immutable in-memory maps.
- Shared memory lives in a private store. Migration is copy-only.
- `kingstack release --build` writes a content-addressed directory under a
  caller-supplied private runtime.
- `kingstack release --activate` and `--rollback` work only under that private
  runtime. They refuse `~/.claude`, `~/.codex`, and `~/.cursor`.

## What is not done

- No live activation of any native home
- No Superpowers plugin disablement
- The six plan files still exist
- This branch is not pushed

## What Hassan must approve before any live link

1. The exact owned paths for Claude and Codex.
2. That rollback is proven on a throwaway home first. Private-runtime rollback
   is already proven. Live-home rollback is a later step.
3. That the six plan files are deleted only after cutover, never before.
4. Push and merge of `feat/agent-neutral-kingstack`.

Say `approve live link` if you want that work to start. Until then the native
homes stay real directories.
