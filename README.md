# kingstack

Kingstack is how Hassan runs Claude, Codex, and Cursor as one operating
system. Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack)
is the process engine. This repo is the source. The live folders those
agents already use are not.

Work here:

```text
~/Desktop/Work/kingstack
```

Leave these alone unless Hassan has approved a live link:

```text
~/.claude
~/.codex
~/.cursor
```

Those three directories are the native homes. Claude, Codex, and Cursor
already load files from them. This repo builds copies of the files it owns.
It does not write those homes yet. The stop is
[docs/migration/pre-link-briefing.md](docs/migration/pre-link-briefing.md).

If you are new, read [docs/SETUP.md](docs/SETUP.md). Then
[docs/README.md](docs/README.md) for the map.

## What the repo does

Each adapter is a small folder under `adapters/`. The shared policy lives
under `core/`. `./scripts/kingstack render` builds a bundle in memory, a
map of relative paths to bytes. Nothing on disk in a native home changes.

`release` writes that bundle under a runtime directory you pass in.
`activate --dry-run` prints which live files a later link would touch.
`activate` without `--dry-run` still errors if the target is a native home.

pstack skills come from upstream. Do not edit a generated pstack skill.
Put personal rules in `king-mode` or in `core/instructions/`.

## Run these

```bash
cd ~/Desktop/Work/kingstack
./scripts/kingstack setup
./scripts/kingstack check --all --mode staged
./scripts/kingstack render --adapter claude --manifest
./scripts/kingstack status --model opus --effort medium
./scripts/kingstack effort --file transcript.txt
./scripts/kingstack memory list
./scripts/kingstack memory harvest --inbox memory-review.md
./scripts/kingstack memory consolidate
./scripts/kingstack session list
./scripts/kingstack handoff --finish "<done means>"
./scripts/kingstack release --adapter cursor --runtime /tmp/ks --build
./scripts/kingstack activate --adapter cursor --runtime /tmp/ks --release <id> --native-home /tmp/home --dry-run
./scripts/kingstack sync-upstream headroom --check
```

`check --all --mode staged` must print `healthy`.
`check --all --mode live` prints `unhealthy` until a native home is linked.
That is the intended result.

`status` prints one line: folder, model, effort, context size, cost, and
which models subagents used. After a Claude link, that line also becomes
the Claude status bar. Codex has its own footer fields plus this command.
Cursor has only this command.

Memory lives in `~/.kingstack/memory`, not in a native home. Hassan
approves every promote. `memory harvest` and `memory consolidate` write
candidates only. A rejected fact stays rejected until the body
changes. Live jobs across Claude, Codex, and Cursor live in
`~/.kingstack/sessions`. That index holds pointers, not transcripts.
CI runs unit tests and staged health
(`.github/workflows/staged.yml`).

## Adapters

| | Claude | Codex | Cursor |
| --- | --- | --- | --- |
| Guidance file | `CLAUDE.md` | `AGENTS.md` | `rules/kingstack/*.mdc` |
| Bundled skills | 54 | 37 | 54 |
| File it merges, not replaces | `settings.json` (`statusLine` only) | `config.toml` | none |

Codex cannot run 18 skills that need Task, `subagent_type`, or `/loop`.
The catalog lists them as unsupported. That is the honest count, not a
half-built adapter. Cursor does not get Cloudflare plugins it does not
install.

Headroom is pinned like pstack. The pin is `headroom-upstream.txt`.
Large tool output is archived under `~/.kingstack/headroom`. Retrieve with
`kingstack headroom retrieve <id>`. No wrap, no image crush.

The only ownership list is `adapters/<id>/owned-paths.json`. If render,
release, and activation disagree, staged health fails.

## New machine

A teammate follows [docs/SETUP.md](docs/SETUP.md). Hassan's default
checkout is still `~/Desktop/Work/kingstack`.

```bash
git clone https://github.com/hassanGH-GG/kingstack
cd kingstack
./scripts/kingstack setup
```

Do not clone this repo into `~/.claude`.

## Rules that keep it honest

- Do not edit a pstack skill by hand. The next sync overwrites it.
- A correction is a design defect. Fix the structure, or add a test, or
  add a rule. Do not paper over it.
- One place per fact. Shared memory is `~/.kingstack/memory`. Identity
  is `core/instructions/`. Process is pstack. Taste is `king-mode`.
- Use the cheapest model that can do the work. Keep the main thread on
  medium effort unless Hassan says otherwise.
- After you change this checkout, run
  `./scripts/kingstack check --all --mode staged`.

## Provenance

pstack is Lauren Tan's, MIT, copied from `cursor/plugins`. The last synced
commit is the first line of `pstack-upstream.txt`. The rest is Hassan's
unless a file says otherwise.
