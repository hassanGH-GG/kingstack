# Sweeps registry (absorbed from minions' feat-watch pattern)

One file per recurring unattended check. The **frontmatter** is what `scripts/run-sweeps.sh`
reads; the **body** is the prompt the agent runs. Adding a sweep is a markdown file and a
commit. Each sweep runs in its own headless session, so one failure never takes down the rest.

| field | meaning |
|---|---|
| `name` | key; must equal the filename |
| `enabled` | `true`/`false`; disabled entries are listed, not run |
| `schedule` | `daily` / `weekly` / `manual` (the launchd job runs daily; weekly entries fire on Monday) |
| `cwd` | directory the session runs in (project checkout); `~` allowed |
| `model` | per model-routing: `haiku` for lookup/summarize sweeps, `opus`/`fable` for judgment |
| `max_turns` | hard bound; every sweep MUST have one |
| `report` | where the result goes: `log` (default), `memory-inbox`, or `file:<path>` |
| `owner` | who reads the result |
| `allow` | comma-separated extra permission rules the sweep needs, e.g. `Bash(./scripts/kingstack check*)`. Read-only tools are always allowed; `bypassPermissions` is never used. |

Body = the exact prompt. Write it for an unattended session: what to check, what "nothing
to report" looks like, and the one-line shape of the result. See `_template.md`.
