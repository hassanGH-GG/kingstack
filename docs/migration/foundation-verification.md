# Neutral foundation verification

Verified on 2026-08-20 before any adapter activation, native-path link, or
configuration merge.

## Acceptance result

The neutral foundation passed its acceptance gate. The canonical checkout was
fast-forwarded from bootstrap commit
`94ad81cdb5d026cc7620272962a8998b0adf6d09` to the independently reviewed
source commit `893ff893725ba7937acf52ad279a3bf373d71d74` through a Git bundle.
This copied Git objects without hardlinks. The canonical branch, GitHub origin,
upstream, tags, and pre-existing untracked redacted baseline were preserved.

- Canonical and reviewed-source HEAD: `893ff893725ba7937acf52ad279a3bf373d71d74`
- Branch: `feat/agent-neutral-kingstack`
- Origin: `https://github.com/hassanGH-GG/kingstack.git`
- Upstream: `origin/feat/agent-neutral-kingstack`
- Tag count: `0`
- Object alternates: none
- Temporary source remotes or configured source-worktree paths: none
- Multi-linked Git object files after import: none

`git fsck --full` exited zero for the canonical checkout, reviewed source, and
legacy Claude repository. Each reported the same four harmless unreachable
objects: three dangling trees and one dangling blob. No corruption was found.

## Public inventory

The tracked candidate `docs/baselines/claude-codex-baseline.json` is
byte-identical to both a fresh live inventory and the baseline named by the
private bootstrap manifest.

- Baseline SHA-256: `8d943deaa440a279452e3af79400c6651722306936d2d90922692810722ddf27`
- Claude records: `587`
- Codex records: `434`
- Claude memory banks: `14`
- Absolute home-path matches: `0`
- Credential-shaped value matches: `0`
- JSON schema/version check: passed (`version: 1`)

The inventory records relative paths, modes, kinds, redacted link targets,
configuration key paths, and content hashes. It contains no configuration
scalar values.

## No-loss evidence

The same ten protected live files hashed after Task 4 were hashed again before
this gate. All ten hashes are byte-identical: Claude's global instructions and
settings, seven indexed project memory files, and Codex's configuration. Both
native homes remain real directories, and no top-level native-home link was
created.

All ten historical private top-level directories remain present with the same
names:

- `archive-20260820-121406`
- `archive-20260820-122621`
- `snapshot-20260820-092749`
- `snapshot-20260820-092901`
- `snapshot-20260820-093002`
- `snapshot-20260820-093104`
- `snapshot-20260820-094710`
- `snapshot-20260820-101106`
- `snapshot-20260820-105637`
- `snapshot-20260820-113207`

Foundation permissions at acceptance:

| Path | Type | Mode |
|---|---|---:|
| `~/.kingstack` | directory | `0700` |
| `~/.kingstack/bootstrap` | directory | `0700` |
| `~/.kingstack/bootstrap/manifest.json` | regular file | `0600` |
| `~/Desktop/Work/kingstack` | directory | `0755` |
| `~/.claude` | directory | `0700` |
| `~/.codex` | directory | `0755` |

No path under `~/.claude` or `~/.codex` was created, rewritten, renamed,
linked, or removed by this foundation gate. No adapter was activated, no
native configuration was merged, no schedule was changed, Superpowers was not
disabled by this gate, and nothing was pushed.

## Verification commands

The complete foundation suite passed:

```text
Ran 31 tests in 14.891s
OK
```

The plan-exact inventory command wrote a fresh temporary report and byte
comparison passed. Canonical, source, and legacy `git fsck --full` each exited
zero. Protected hashes and historical top-level names matched their Task 4
evidence byte-for-byte.

## Pre-existing legacy health drift

The current legacy `~/.claude/scripts/check-setup.sh` correctly returned drift,
not `SETUP HEALTHY`. It reported exactly two failures that predate bootstrap:

```text
stray ~/.claude/.claude.json exists (breaks headless login)
kingstack differs from origin/main
```

The legacy repository remains at
`cfebf985dcf9a5c40f556ea81d2b71d306bdcfeb`, ahead of and different from its
GitHub `origin/main`. This gate did not delete the stray file, rewrite legacy
Git history, pull, push, or otherwise repair either drift. Recording them
honestly prevents a pre-existing condition from being mistaken for migration
damage.
