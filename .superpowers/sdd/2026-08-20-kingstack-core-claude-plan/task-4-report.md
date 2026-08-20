# Task 4 report — single-source skills and adapter-neutral pstack

Base: `9d5e48b51eb495970358485e6b3f6010640bcb64`

## Baseline gate before source moves

The tree was clean at the exact base. The frozen public inventory and the live
Claude skill directory produced the same exact 65 sorted names, with an empty
diff. Both the tracked stamp and the upstream checkout were `63d938c`.

```text
HEAD=9d5e48b51eb495970358485e6b3f6010640bcb64
STATUS_LINES=0
BASELINE_SKILL_COUNT=65
LIVE_SKILL_COUNT=65
NAME_DIFF_BEGIN
NAME_DIFF_END
PSTACK_TRACKED=63d938c
PSTACK_SOURCE=63d938c
NO_CURRENT_LINK /Users/mac/.claude/current
NO_CURRENT_LINK /Users/mac/.codex/current
NO_CURRENT_LINK /Users/mac/.kingstack/current
```

The pre-change full suite was green:

```text
Ran 84 tests in 9.695s

OK
```

Pre-change protected fingerprints:

```text
7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e  /Users/mac/.claude/CLAUDE.md
d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b  /Users/mac/.claude/settings.json
ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14  /Users/mac/.codex/config.toml
07dd8e646ebb4d3368a48c0e40db31838b9d850e5c0aa02e989aee19fdaffd41  /Users/mac/.claude/pstack-upstream.txt
58ab2ac234426d885e029c74cbdc5f3d1b1250090eda7a52e4391786c97ba999  /Users/mac/.claude/pstack-manifest.sha256
CLAUDE_SKILL_TREE_SHA256 3f669c14d0d792d84b6d36d66dafc3409164bb1159768a077d72ee3b40fb3b27
```

## RED evidence

First RED, before any production file or source move:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_skills -v
test_skills (unittest.loader._FailedTest) ... ERROR

ImportError: Failed to import test module: test_skills
ModuleNotFoundError: No module named 'kingstack.skills'

Ran 1 test in 0.000s
FAILED (errors=1)
```

After the minimal two-test catalog cycle went green, the full behavioral
contract was written before its implementation:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_skills -v
test_skills (unittest.loader._FailedTest) ... ERROR

ImportError: cannot import name 'bundle_manifest' from 'kingstack.skills'

Ran 1 test in 0.000s
FAILED (errors=1)
```

The shell compatibility wrapper had its own isolated-home RED. The old script
attempted its former native sync path and failed safely before any write:

```text
test_sync_pstack_wrapper_is_a_pure_adapter_aware_entry_point ... FAIL
AssertionError: 1 != 0 : no pstack at .../missing/pstack

Ran 1 test in 0.430s
FAILED (failures=1)
```

## Implementation and GREEN evidence

- `core/skills/catalog.json` is the authoritative 65-entry catalog: 43 pstack,
  8 adopted, 2 kingstack-authored, and 12 plugin-managed.
- `king-mode` and `memory-review` moved byte-for-byte into
  `core/skills/authored/`.
- Catalog validation rejects schema drift, bad owners/targets, portable aliases,
  unsafe paths and symlinks, bad/missing frontmatter and sources, dependency
  gaps/cycles, and owner/source contradictions.
- Claude and Codex named transform documents permit only frontmatter, host,
  model, tool, and path rules, then reject remaining foreign-host terms.
- Rendering returns immutable in-memory maps. Plugin-managed content is
  accounted for but never copied.
- The pstack wrapper now delegates only to the pure `sync-upstream` command. It
  does not pull, stage, install, prune, activate, or write a native home.
- Clobber checking is read-only and refuses changed generated files or manifests
  claiming kingstack-authored/plugin-managed paths.

Final focused and regression output:

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_skills -q
Ran 11 tests in 3.287s

OK

$ PYTHONPATH=lib python3 -m unittest tests.test_skills tests.test_routing tests.test_instruction_render tests.test_adapter_contract -q
Ran 64 tests in 7.728s

OK
```

Final full-suite output:

```text
$ PYTHONPATH=lib python3 -m unittest discover -s tests -q
Ran 95 tests in 18.816s

OK
```

## CLI, ownership, and semantic evidence

Both the pure upstream check and the optional read-only live clobber check
returned the same result:

```json
{
  "schema_version": 1,
  "semantics": {
    "claude": [],
    "codex": []
  },
  "upstream": {
    "revision": "63d938c",
    "status": "clean",
    "upstream": "pstack"
  }
}
```

Exact bundle and full-render accounting:

```text
claude sync:  skills=65 bundled=53 plugin-managed=12 unsupported=0 files=130 SKILL.md=53
claude render: skills=65 bundled=53 plugin-managed=12 unsupported=0 files=131 SKILL.md=53 guidance=CLAUDE.md
codex sync:   skills=65 bundled=53 plugin-managed=11 unsupported=1 files=130 SKILL.md=53
codex render: skills=65 bundled=53 plugin-managed=11 unsupported=1 files=131 SKILL.md=53 guidance=AGENTS.md
```

The one Codex unsupported record is the Claude-only package-managed
`service-migration-handover`. The 12/11 package-managed records deliberately do
not become bundle files. This satisfies the stricter ownership requirement; the
older plan probe requiring 65 copied `SKILL.md` files would contradict the rule
that plugin-managed skills must never be copied.

Contract CLI output:

```text
claude adapter contract valid
codex adapter contract valid
example adapter contract valid
```

Direct normalized comparisons returned no errors:

```text
claude: semantic parity errors=0 ()
codex: semantic parity errors=0 ()
authored moves: byte-identical
```

## Static and no-live evidence

```text
py_compile: clean
json: clean core/skills/catalog.json
json: clean core/skills/transforms/claude.json
json: clean core/skills/transforms/codex.json
json: clean adapters/claude/adapter.json
json: clean adapters/codex/adapter.json
shell syntax: clean
pure/no staging scan: clean
git diff --check: clean
```

Final protected-state proof:

```text
/Users/mac/.claude/CLAUDE.md: unchanged sha256=7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e
/Users/mac/.claude/settings.json: unchanged sha256=d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b
/Users/mac/.codex/config.toml: unchanged sha256=ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14
/Users/mac/.claude/pstack-upstream.txt: unchanged sha256=07dd8e646ebb4d3368a48c0e40db31838b9d850e5c0aa02e989aee19fdaffd41
/Users/mac/.claude/pstack-manifest.sha256: unchanged sha256=58ab2ac234426d885e029c74cbdc5f3d1b1250090eda7a52e4391786c97ba999
Claude live skill tree: unchanged aggregate sha256=3f669c14d0d792d84b6d36d66dafc3409164bb1159768a077d72ee3b40fb3b27
frozen/live Claude skill names: exact 65, no diff
/Users/mac/.claude: real directory
/Users/mac/.codex: real directory
/Users/mac/.kingstack: real directory
/Users/mac/.claude/current: absent (no activation link)
/Users/mac/.codex/current: absent (no activation link)
/Users/mac/.kingstack/current: absent (no activation link)
/Users/mac/.kingstack/adapters/claude/current: absent (no activation link)
/Users/mac/.kingstack/adapters/codex/current: absent (no activation link)
native/live type-link proof: clean
```

No path under `~/.claude`, `~/.codex`, or `~/.kingstack` was created,
rewritten, renamed, linked, activated, or removed. No mutable `.staging`, release
materialization, schedule change, Superpowers change, six-plan deletion, push,
or activation occurred.
