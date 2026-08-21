<!-- local-edit: control-cli-field-notes -->

## Field notes (local)

Hard-won corrections to the sections above. They apply before the generic loop, not after it.

**Harness options: tmux is the proven first rung for a TUI.** Reach for it before any PTY
library. Three failure modes are durable, not incidental:

- PTY-library spawn helpers (`pty.spawn`, node-pty wrappers) often fail outright in sandboxes.
- `expect` and raw `pty.openpty()` need a post-spawn `stty rows <n> cols <n>` on the slave TTY,
  or the app lays out against an 80x24 phantom and every capture is wrong.
- Every capture needs ANSI stripped before you read or diff it. Raw escape bytes make a
  matching screen look different and a differing screen look the same.

**Harness loop, before step 3: gate on the build.** Before spawning anything, grep the repo for
existing capture or snapshot tests, and for a build/bundle step. Driving a stale build artifact
silently invalidates every capture you take after it.

**Profiling, first step: enumerate the framework's render defaults.** List the TUI framework's
frame throttle, diffing strategy, alt-screen use, and synchronized-update support, plus the
options it exposes, before measuring or patching anything. A defaulted frame throttle is the
first suspect for "feels laggy".

**What it is used for: capturing a reference CLI is first-class.** Capture the baseline binary
under the same harness before designing parity work; that capture is a blocking prerequisite.
A prose description of a competitor's CLI is not a design basis.

**Guardrails: suspect the host emulator before the code.** When the user's terminal behaves
differently from the harness PTY, look at their emulator and environment first (VS Code's
tab-focus mode eating Tab, for example). Any keybinding a host can steal ships with a
designed-in fallback binding.
