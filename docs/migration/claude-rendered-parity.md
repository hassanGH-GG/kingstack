# Rendered Claude parity

Adapter: `claude`

This report compares capability IDs, not raw file counts. Skills and lifecycle
hooks must appear in the in-memory bundle. Helper commands, schedules, sweeps,
agents, and the live 200k / medium policy remain live-preserved until later
phases materialize them.

Required ID families:

- 65 Claude skill names
- five lifecycle hooks
- 16 helper commands
- three launchd schedules
- four sweep definitions
- two pstack agents
- eight instruction fragments
- compaction 200k, medium effort, pstack `4612556`

Run:

```bash
./scripts/kingstack check --rendered --adapter claude
```

A missing ID fails the command. Approved filename-only transforms are not
present in this phase. No live path is written.
