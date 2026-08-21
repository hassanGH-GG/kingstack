# Pre-link briefing

Status: approved by Hassan on 2026-08-21 (setup, migrate, make all 3 work, clean ~/.claude).
Hassan's three homes are linked. The six dated plan files are gone.
A teammate follows `docs/SETUP.md` and only needs this file when they
are about to write a native home.

This was the last stop before anyone wrote `~/.claude`, `~/.codex`, or
`~/.cursor`. Live apply now takes `--apply --approved-briefing` pointing
at this file.

## What kingstack would own

The only list is `adapters/<id>/owned-paths.json`.

| Adapter | Files it would replace | Files it would merge | Extra file used for the merge |
| --- | --- | --- | --- |
| Claude | `CLAUDE.md`, hooks including `ctx-status.py`, `bin/claude-check`, `bin/kingstack-path`, 54 skill directories | `settings.json`: `statusLine` and `hooks` | `settings-owned.json` |
| Codex | `AGENTS.md`, hooks including `ctx-status.py`, `bin/kingstack-path`, 37 skill directories | `config.toml`, owned keys plus the footer field list | `config-owned.json` |
| Cursor | `rules/kingstack/*.mdc`, hooks including `ctx-status.py` and a Cursor-native `hooks.json`, `bin/kingstack-path`, 54 skill directories | none | none |

It will not take the whole home. Claude `projects`, `memory`, `auth.json`,
`sessions`, `plugins`, and `cache` stay yours. Codex `auth.json`,
`sessions`, `memories`, `tmp`, and `plugins` stay yours. Cursor
`projects`, `ai-tracking`, `extensions`, `argv.json`, `skills-cursor`,
`chats`, and `cli-config.json` stay yours.

## What is already proven

Rollback of a merge keeps keys kingstack does not own. If you add `theme`
after an apply, rollback keeps `theme` and removes `statusLine`.

If apply fails after a rename, a merge, or the `current` switch, the temp
home goes back to what it was. Apply against `~/.claude` still raises.

If two schedule owners start the same job, the intended result is
`duplicate prevented`. The lock is still check-then-write; treat a
stolen schedule as an open item, not a closed proof.

`claude-check` and `kingstack-path` ship inside a release. They are not
linked into a live home.

The curated Claude memory banks are copied into `~/.kingstack/memory`.
Each bank uses the real project path as its id. The live Claude banks
were not changed.

Headroom is pinned at `headroom-upstream.txt`. Fat tool text is archived
under `~/.kingstack/headroom`, not in a native home. Images are not
crushed. PreCompact and SessionStart keep archive ids and drop the raw
blob. Retrieve with `kingstack headroom retrieve <id>`.

`kingstack setup` prepares `~/.kingstack` and never writes a native home.
A personal profile skips the king-mode overlay. Hassan's default checkout
is still `~/Desktop/Work/kingstack`. A teammate follows `docs/SETUP.md`.

`kingstack status` prints folder, model, effort, context, cost, and the
models subagents used. After a Claude link, that becomes the status bar.
Codex keeps its own footer and can still run the command. Cursor only
has the command. `kingstack effort --file` scans `↳ spawn` lines. Inherit
is fail.

`kingstack memory harvest` and `kingstack memory consolidate` write
candidates only. Hassan still promotes. `kingstack session` lists live
jobs under `~/.kingstack/sessions`. Pointers only. `kingstack handoff`
writes a packet for Codex.

CI runs unit tests and `check --all --mode staged`. That job is on GitHub
once this branch is pushed.

## What Hassan has to approve

1. The ownership table, including `statusLine` as the only Claude
   settings key kingstack will write.
2. That the temp-home apply and rollback proofs are enough.
3. That the six dated plan files get deleted only after a live link
   holds, never before.
4. Push and merge of `feat/agent-neutral-kingstack`.

Hassan approved the live link on 2026-08-21. Activate with
`--apply --approved-briefing docs/migration/pre-link-briefing.md`.
