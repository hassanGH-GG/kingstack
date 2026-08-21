# kingstack

Kingstack is how Hassan runs Claude, Codex, and Cursor as one operating
system. Lauren Tan's [pstack](https://github.com/cursor/plugins/tree/main/pstack)
is the process engine. This repo is the source. The live folders those
agents already use are not.

Work here:

```text
~/Desktop/Work/kingstack
```

If you are new, read [docs/SETUP.md](docs/SETUP.md). Then
[docs/README.md](docs/README.md) for the map.

## Why this exists

Three products, three homes, three copies of the same rules. For a while
`~/.claude` *was* the git repo. That made a teammate, a second laptop, and
CI all special cases. A correction in one home died in the others.

This checkout is the public source. `~/.claude`, `~/.codex`, and
`~/.cursor` stay the folders those products already read. A live link
writes only the paths in each adapter's `owned-paths.json`. Unowned keys,
comments, and plugin lists stay. Rollback is a first-class path, not a
hope.

pstack is the one process door. Superpowers stays off so a second
framework cannot steal the first turn. Shared memory and the session
index live under `~/.kingstack`, not inside a vendor home, so a fact
approved in Claude is still there when Codex or Cursor picks up the
same project.

A correction is a design defect. The next agent should hit a type, a
test, or a check, not a chat note.

## What it can do

| Capability | What you get |
| --- | --- |
| Render, release, activate | Build a bundle in memory. Stamp a release. Write only owned paths. Mixed files merge and invert. |
| Setup | Prepare `~/.kingstack` and `~/.local/bin/kingstack`. Never write a native home. |
| Health | `check --mode staged` is the checkout. `check --mode live` is each home that exists and is linked. Superpowers off is a live row. |
| Memory | `~/.kingstack/memory`. Harvest and consolidate write candidates. Hassan promotes. A rejected fact stays rejected until the body changes. |
| Sessions | Cross-adapter working set under `~/.kingstack/sessions`. Pointers, not transcripts. `close` and `sweep` mark leftovers done. |
| Handoff | Write a Codex packet from the current finish condition. |
| Headroom | Archive tool text over about 30KB. Retrieve by id. No wrap. No image crush. |
| Effort | Scan `↳ spawn` lines. A named model and effort pass. `inherit` fails. |
| Status | One line of folder, model, effort, context, cost, and subagent models. Claude can use that line as the status bar. |
| Secrets | Inbox, compaction checkpoints, and session prompts drop secret-like lines and write those files `0o600`. |
| Process | poteto-mode picks the playbook. king-mode is Hassan's overlay. Routing lives in `model-routing.md`. |

## What the repo does

Each adapter is a small folder under `adapters/`. The shared policy lives
under `core/`. `./scripts/kingstack render` builds a bundle in memory, a
map of relative paths to bytes. Render itself does not write a native home.

`release` writes that bundle under a runtime directory you pass in.
`activate --dry-run` prints which live files a link would touch.
`activate --apply --approved-briefing docs/migration/pre-link-briefing.md`
writes those files.

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
./scripts/kingstack session close <id>
./scripts/kingstack session sweep
./scripts/kingstack handoff --finish "<done means>"
./scripts/kingstack release --adapter cursor --runtime /tmp/ks --build
./scripts/kingstack activate --adapter cursor --runtime /tmp/ks --release <id> --native-home /tmp/home --dry-run
./scripts/kingstack sync-upstream headroom --check
```

`check --all --mode staged` must print `healthy`.
`check --all --mode live` prints `healthy` after each native home that
exists on the machine is linked. Homes you do not have are skipped.

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
| File it merges, not replaces | `settings.json` (status line, hooks, Superpowers off) | `config.toml` | none |

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

Setup writes `~/.local/bin/kingstack`. Put `~/.local/bin` on `PATH`,
then run `kingstack check --all --mode staged`. That must print
`healthy`. Do not clone this repo into `~/.claude`.

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
