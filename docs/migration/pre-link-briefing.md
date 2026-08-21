# Pre-link briefing

Status: WAITING FOR HASSAN

This is the Super Saiyan 3 stop. Nothing under `~/.claude`, `~/.codex`, or
`~/.cursor` has been linked or replaced. Throwaway apply is proven. Live
apply is still refused.

## Ownership

`adapters/<id>/owned-paths.json` is the only ownership document.

| Adapter | Fully owned live paths | Mixed live files | Mixed payloads |
| --- | --- | --- | --- |
| Claude | `CLAUDE.md`, hooks, 53 skill directories | `settings.json` | none |
| Codex | `AGENTS.md`, hooks, 36 skill directories | `config.toml` | `config-owned.json` |
| Cursor | `AGENTS.md`, hooks, 53 skill directories | none | none |

Render may emit only `fully_owned` plus mixed payloads. Activation plans
only `fully_owned` and `mixed`. Staged health fails if those sets disagree.
Whole-home ownership stays illegal.

Forbidden trees stay untouched: Claude `projects`, `memory`, `auth.json`,
`sessions`, `plugins`, `cache`. Codex `auth.json`, `sessions`, `memories`,
`tmp`, `plugins`. Cursor `projects`, `ai-tracking`, `extensions`, `argv.json`.

## Throwaway apply evidence

`apply_activation` writes a dated sibling for every fully owned path, merges
mixed files, and publishes `.kingstack-current` under a temp home.

- Fake release ids fail. `activate --release deadbeef --dry-run` exits 2.
- `apply_activation` on `~/.claude` raises.
- Injected failure after rename restores the pre-state.
- A second apply of the same release is a no-op.
- `kingstack release --select --to <id>` retargets private `current` only.

## What is ready

- Claude, Codex, and Cursor stay first-party adapters. Codex still records
  the 18 Task/loop skills as unsupported.
- Shared memory candidates hash adapter, project, and content. Session is
  metadata. A rejected content hash does not return.
- Memory migrate is copy-only. Apply is proven against a temp store, not
  `~/.kingstack/memory`.
- `kingstack check --all --mode staged` is healthy. `--mode live` stays
  unhealthy on real native homes.
- `--rendered` parity compares the checkout baseline, not today's live home.

## What is not done

- No live activation of any native home
- No copy into the real `~/.kingstack/memory`
- No Superpowers plugin disablement
- The six plan files still exist
- This branch is not pushed

## What Hassan must approve before any live link

1. The ownership table above.
2. That throwaway apply and rollback are enough evidence to proceed.
3. That the six plan files are deleted only after cutover, never before.
4. Push and merge of `feat/agent-neutral-kingstack`.

Say `approve live link` if you want that work to start. Until then the native
homes stay real directories.
