# Pre-link briefing

Status: WAITING FOR HASSAN

This is the complete-before-link stop. Native homes were not written.
Throwaway apply, inverse mixed rollback, schedule locks, release wrappers,
shared memory copy, and the portable context status line are in the
checkout.

## Ownership

`adapters/<id>/owned-paths.json` is the only ownership document.

| Adapter | Fully owned live paths | Mixed live files | Mixed payloads |
| --- | --- | --- | --- |
| Claude | `CLAUDE.md`, hooks including `ctx-status.py`, `bin/claude-check`, `bin/kingstack-path`, 53 skill directories | `settings.json` (`statusLine` only) | `settings-owned.json` |
| Codex | `AGENTS.md`, hooks including `ctx-status.py`, `bin/kingstack-path`, 36 skill directories | `config.toml` (owned keys plus `tui.status_line`) | `config-owned.json` |
| Cursor | `AGENTS.md`, hooks including `ctx-status.py`, `bin/kingstack-path`, 53 skill directories | none | none |

Forbidden trees stay untouched. Whole-home ownership stays illegal.

## What landed before any live link

- Inverse mixed rollback keeps unowned keys. A `theme` or `keepAfter` key
  added after apply survives rollback. `statusLine` is removed.
- Throwaway fault injection after rename, mixed publish, and `current`
  restores the pre-state. Native `~/.claude` apply still raises.
- Schedule locks live under `~/.kingstack/manifests/schedules`. A second
  owner prints `duplicate prevented`.
- Release wrappers resolve through `KINGSTACK_ROOT`. They are in the
  bundle, not linked live.
- Curated Claude banks were copied into `~/.kingstack/memory`. Identity
  is the real project path, not the hyphen slug under `~/.claude/projects`.
  A parent-git collision that smashed every bank into one id is fixed.
  Live Claude banks were not modified.
- `kingstack status` is the same cache-read cost math on every adapter.
  Claude will run it as `settings.json` `statusLine` after a link. Codex
  owns native `tui.status_line` fields plus the same command. Cursor has
  no native footer hook; it uses `kingstack status` / `hooks/ctx-status.py`.

## What Hassan must approve before any live link

1. The ownership table, including `statusLine` as the only Claude settings key.
2. That throwaway apply and inverse rollback are enough evidence.
3. That the six plan files are deleted only after cutover.
4. Push and merge of `feat/agent-neutral-kingstack`.

Say `approve live link` if you want that work to start. Until then the native
homes stay real directories.
