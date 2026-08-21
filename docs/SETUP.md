# Set up kingstack on a new machine

This is the how-to for a teammate. Clone the repo anywhere. One command
prepares a private runtime and puts `kingstack` on a local bin path. It
does not write `~/.claude`, `~/.codex`, or `~/.cursor`.

## What you will have

- poteto-mode, the three adapters, routing, and Headroom CCR
- an empty memory store under `~/.kingstack/memory`
- an empty session index under `~/.kingstack/sessions`
- a wrapper at `~/.local/bin/kingstack` that runs this checkout
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

You should see `staged: healthy` and a `cli:` line pointing at
`~/.local/bin/kingstack`. Setup writes only `~/.kingstack` and that
wrapper. It does not import Claude, Codex, or Cursor chats.

If the pstack checkout (`plugins`) or Headroom is missing, the output
prints one `git clone` line each. Clone them as siblings of this repo,
or set `KINGSTACK_UPSTREAM_ROOT`, then run setup again.

3. Put the wrapper on `PATH` if setup printed `put ~/.local/bin on PATH`.

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Add that line to your shell rc so new terminals keep it.

4. Confirm the checkout and the wrapper.

```bash
./scripts/kingstack check --all --mode staged
command -v kingstack
kingstack check --all --mode staged
```

Both checks must print `healthy`. `command -v kingstack` must print
`~/.local/bin/kingstack`.

`check --all --mode live` stays `unhealthy` until you link a native
home you already use. Homes that do not exist are not required. That
is intended.

Useful later:

```bash
kingstack status
kingstack effort --file transcript.txt
kingstack memory list
kingstack session list
kingstack session close <id>
kingstack session sweep
kingstack handoff --finish "<done means>"
kingstack headroom retrieve <id>
```

Hassan's checkout default is still `~/Desktop/Work/kingstack`. Yours can
be any directory. Set `KINGSTACK_ROOT` if hooks cannot see the clone.

## Link a native home

Do this only if you want Claude, Codex, or Cursor to load kingstack
files. Read [migration/pre-link-briefing.md](migration/pre-link-briefing.md)
first. Then build a release and apply it.

```bash
./scripts/kingstack release --adapter cursor --runtime ~/.kingstack --build
./scripts/kingstack activate --adapter cursor --runtime ~/.kingstack \
  --release <id> --native-home ~/.cursor \
  --apply --approved-briefing docs/migration/pre-link-briefing.md
```

Repeat for `claude` → `~/.claude` and `codex` → `~/.codex` if you use
those agents. Then run:

```bash
kingstack check --all --mode live
```

That prints `healthy` when every native home that exists on this
machine is linked, and when the CLI wrapper is in place.

## Optional

```bash
./scripts/kingstack setup --identity hassan
```

That turns king-mode on as an overlay for this machine only.

Do not copy this repo into `~/.claude`. Hassan's machine is already
linked. A teammate stays unlinked until they run activate themselves.

## Another machine

Copy or sync `~/.kingstack` (profile, memory, sessions, Headroom archives, releases).
Clone the repo. Run `./scripts/kingstack setup` again. That rewrites the
wrapper to this clone. Native homes stay on the machine that runs the
agent. Do not copy `~/.claude`, `~/.codex`, or `~/.cursor`.
