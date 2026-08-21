# Task 5–6 report — portable lifecycle hooks and Claude parity

Base: `8541cfd901408c488ee7c447dc91b296a50729fb`

## RED

```text
ImportError: No module named 'kingstack.hooks'
ImportError: No module named 'kingstack.parity'
AssertionError: 'hooks/run.py' not found in Claude bundle
```

## GREEN

```text
PYTHONPATH=lib python3 -m unittest tests.test_hook_contracts tests.test_rendered_bundle_syntax tests.test_claude_parity
Ran 10 tests in 0.394s after parity fix
OK

PYTHONPATH=lib python3 -m unittest discover -s tests -q
Ran 117 tests in 12.155s
OK

./scripts/kingstack check --rendered --adapter claude
ok True ids 106 mismatches []
```

Claude bundle now includes the eight hook files. Plugin-managed skills stay
live-preserved. Helper commands, schedules, sweeps, and agents stay
live-preserved. No activation, no current link, no `.staging` writer.

Protected hashes after this work:

```text
CLAUDE.md MATCH 7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e
settings.json MATCH d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b
config.toml MATCH ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14
```

Cursor Agent adapter is recorded as Phase H in the handoff and was not
implemented.
