# Set up kingstack on a new machine

This is the path for a teammate. Clone the repo anywhere. One command
prepares a private runtime. It does not write `~/.claude`, `~/.codex`,
or `~/.cursor`.

## What you will have

- poteto-mode, the three adapters, routing, and Headroom CCR
- an empty memory store under `~/.kingstack/memory`
- an empty session index under `~/.kingstack/sessions`
- staged health, or the one row that failed

## What you will not have

- Hassan's memory bank or Headroom archives
- king-mode as an auto-run overlay (that is his identity)
- a live write to a native home

## Steps

1. Clone the repo and enter it.

```bash
git clone https://github.com/hassanGH-GG/kingstack
cd kingstack
```

2. Run setup. Default identity is `personal`.

```bash
./scripts/kingstack setup
```

You should see `staged: healthy`. Setup writes only `~/.kingstack`.
It does not import Claude, Codex, or Cursor chats or their automatic
memory.

If the pstack checkout (`plugins`) or Headroom is missing, the output
prints one `git clone` line each. Clone them as siblings of this repo,
or set `KINGSTACK_UPSTREAM_ROOT`, then run setup again.

3. Confirm the checkout.

```bash
./scripts/kingstack check --all --mode staged
```

That must print `healthy`. `check --all --mode live` prints `unhealthy`
until a native home is linked. That is intended.

Useful later:

```bash
./scripts/kingstack effort --file transcript.txt
./scripts/kingstack memory list
./scripts/kingstack session list
./scripts/kingstack handoff --finish "<done means>"
./scripts/kingstack headroom retrieve <id>
```

Hassan's checkout default is still `~/Desktop/Work/kingstack`. Yours can
be any directory. Set `KINGSTACK_ROOT` if hooks cannot see the clone.

## Optional

```bash
./scripts/kingstack setup --identity hassan
```

That turns king-mode on as an overlay for this machine only.

A live link is a later approve. Do not copy this repo into `~/.claude`.

## Another machine

Copy or sync `~/.kingstack` (profile, memory, sessions, Headroom archives, releases).
Clone the repo. Run `./scripts/kingstack setup` again. Native homes stay on
the machine that runs the agent. Do not copy `~/.claude`, `~/.codex`, or
`~/.cursor`.
