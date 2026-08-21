# Handoff

Date: 2026-08-21
Branch: `feat/agent-neutral-kingstack`
Checkout: `/Users/mac/Desktop/Work/kingstack`

If you did not write this branch, start with [../README.md](../README.md),
then [pre-link-briefing.md](pre-link-briefing.md). Do not write a native
home. Do not push unless Hassan says `push`.

## How we got here

Kingstack used to live in `~/.claude`. Editing source changed the next
Claude session immediately. Codex could not use the same rules without a
copy that would drift. There was no release.

The repo now holds the source. Render builds a bundle in memory. A
release is a folder named by its digest, written where you asked. A
later link may touch only the paths in `owned-paths.json`. Claude,
Codex, and Cursor each have an adapter. The live homes stay real
directories.

## What is true today

Ownership, private `release --select`, merge of mixed config, apply on a
temp home, and memory ids are one system.

Rejected memory stays rejected until the body changes. A teammate starts
with an empty `~/.kingstack/memory`. Hassan's promoted facts live only
in his private runtime, not in this repo.

`kingstack check --all --mode staged` is healthy.
`kingstack check --all --mode live` is unhealthy on purpose.

`apply_activation` raises if the target is `~/.claude`, `~/.codex`, or
`~/.cursor`.

Version is 0.4.0. `kingstack setup` prepares `~/.kingstack`. A personal
profile skips the king-mode overlay. Headroom evicts raw blobs at compact.
`kingstack effort` scans spawn lines. `kingstack session` lists the
working-set index. `kingstack handoff` writes a Codex packet. CI is
`.github/workflows/staged.yml`.

Codex lists 18 Task and loop skills as unsupported. Cursor guidance is
`rules/kingstack`, not a home-root AGENTS.md. Cursor does not get
plugins it does not have. Bundled skills are 54 / 37 / 54.

Superpowers is still on. The six dated plan files are still in the repo.
This branch is not on the remote.

## Commands you will actually run

```bash
./scripts/kingstack setup
./scripts/kingstack check --all --mode staged
./scripts/kingstack status --model opus --effort medium
./scripts/kingstack effort --file transcript.txt
./scripts/kingstack memory list
./scripts/kingstack memory harvest --inbox memory-review.md
./scripts/kingstack memory consolidate
./scripts/kingstack session list
./scripts/kingstack handoff --finish "<done means>"
./scripts/kingstack activate --adapter claude --runtime /tmp/ks --release <id> --native-home /tmp/home --dry-run
```

A fake release id exits 2.

## Leave these alone

- Writes under `~/.claude`, `~/.codex`, or `~/.cursor`
- A `current` symlink on a native home
- Disabling Superpowers
- Deleting the six dated plan files
- A rewrite of pstack
- A fourth adapter
- A restore command that walks a whole home

Hassan says `approve live link` or `push`. Until then, stop at the
briefing.
