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

## Reviewer fix round 1 — source and parity boundaries

Fix base: `190587cd76a74f40a30b8efe4b43ff810d486996`

### Grouped RED before production edits

Seven deterministic tests were added before production changes. The grouped run
failed in every requested architectural category:

```text
Ran 7 tests in 1.577s
FAILED (failures=12, errors=1)

1. symlinked root ancestor accepted
2. malformed frontmatter flow/control/ambiguous/unterminated values accepted
3. destructive catch-all transform accepted; parity depended on render logic
4. empty/missing/extra manifests and extra installed resources accepted/misclassified
5. Codex claimed foreign-host workflow skills as bundled
6. synthetic `example` adapter rejected by a hardcoded target set
7. both adapters broadly claimed the mixed-ownership `skills` tree
```

### Architectural corrections

- Catalog JSON, transform JSON, and every owned source tree are read through
  component-wise `openat` descriptors with `O_NOFOLLOW`. Files, directories,
  source roots, and repository/upstream roots are identity-revalidated after
  reads. Symlinked ancestors and deterministic in-tree source swaps fail closed.
- Loaded source bytes are immutable snapshots; rendering never reopens a source
  by pathname. Production skill code contains no `Path.resolve` or `os.walk`.
- Frontmatter uses a dependency-free strict subset parser: exact keys, no
  duplicates/control characters/ambiguous spacing, quoted scalar termination,
  safe plain scalars, and indented block scalars. All 53 real portable source
  trees parse successfully.
- Transform declarations now use typed exact operations. Frontmatter rules only
  remove named frontmatter fields. Model/tool/host replacements use token
  boundaries; path replacements use exact strings. Empty, catch-all,
  self-mapping, destructive, regex-shaped, and non-host host rules are rejected.
  Every transformed `SKILL.md` is reparsed.
- Semantic parity independently aligns original and rendered content using only
  declared token pairs. It compares resource sets, frontmatter fields/values,
  headings, instruction paragraphs, binary bytes, and normalized script
  content. It never renders an expected value with the transformation engine.
- The clobber manifest must equal the complete pstack/adopted resource set.
  Empty, missing, extra, out-of-catalog, deleted, additional, changed, or
  symlinked installed content is rejected through descriptor reads; caller paths
  cannot expand ownership.
- Adapter IDs come from validated declarations and matching transform documents.
  A synthetic `example` adapter renders `memory-review` and emits a bundle
  manifest without a first-party provider import or core source change.
- Adapter `owned_paths` enumerate only generated skill directories. They never
  claim the broad `skills` tree, plugin-managed directories, or Codex-unsupported
  directories.

### Honest Codex accounting

Codex directly excludes 11 portable skills, plus dependent `king-mode`; the
Claude-only plugin skill remains unsupported. Exact direct evidence is carried
in the manifest:

```text
arena: SKILL.md [run_in_background]
automate-me: SKILL.md [AskQuestion, agent-transcripts]
how: SKILL.md [subagent_type]
interrogate: SKILL.md [Task syntax, subagent_type]
no-comments: SKILL.md [subagent_type]
poteto-mode:
  SKILL.md [subagent_type, run_in_background, /loop]
  playbooks/orchestrate.md [Task syntax, AskQuestion, agent-transcripts]
  playbooks/autonomous-run.md [AskQuestion, /loop]
  playbooks/babysit.md, bug-fix.md, shipping.md, visual-parity.md [/loop]
  playbooks/eval.md, session-pickup.md [agent-transcripts]
  references/plan.md [subagent_type, AskQuestion]
  scripts/worktree-audit.sh [agent-transcripts]
recall: SKILL.md [agent-transcripts]
reflect: SKILL.md [subagent_type, agent-transcripts]
show-me-your-work: SKILL.md [agent-transcripts]
swarm: SKILL.md [subagent_type, run_in_background]
why: SKILL.md [subagent_type]
king-mode: catalog dependency [poteto-mode unsupported]
service-migration-handover: catalog target [Codex not declared]
```

Claude remains the exact frozen 65-name catalog. Final accounting:

```text
claude: skills=65 files=130 bundled=53 plugin-managed=12 unsupported=0 skill_dirs=53
codex:  skills=65 files=48  bundled=41 plugin-managed=11 unsupported=13 skill_dirs=41
claude semantic parity: ()
codex semantic parity: ()
pstack upstream: revision=63d938c status=clean
CLI JSON: claude=65/130, codex=65/48
```

### GREEN and protected-state evidence

```text
$ PYTHONPATH=lib python3 -m unittest tests.test_skills
Ran 18 tests in 6.317s
OK

$ PYTHONPATH=lib python3 -m unittest discover -s tests -v
Ran 102 tests in 20.130s
OK

py_compile: clean
transform/adapter JSON: clean
Path.resolve/os.walk/.staging production scan: clean
git diff --check: clean
```

Protected state remained byte- and type-identical:

```text
CLAUDE.md 7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e
settings.json d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b
config.toml ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14
pstack-upstream.txt 07dd8e646ebb4d3368a48c0e40db31838b9d850e5c0aa02e989aee19fdaffd41
pstack-manifest.sha256 58ab2ac234426d885e029c74cbdc5f3d1b1250090eda7a52e4391786c97ba999
Claude skill tree baseline 3f669c14d0d792d84b6d36d66dafc3409164bb1159768a077d72ee3b40fb3b27 (unchanged; no live writes)
~/.claude, ~/.codex, ~/.kingstack: real directories
all five checked current links: absent
```

No live write, staging directory, native link, release, schedule, activation,
Superpowers change, plan deletion, push, or amend occurred.

## Reviewer fix round 2 — final Task 4 closure

Closure base: `07cd9895ffaf02bdeaf876095127e3ed148b60a5`

The standalone migration handoff was read and preserved byte-for-byte. This
round touched only Task 4 catalog, adapter ownership, loader, tests, and this
append-only report.

### Grouped RED before production edits

Five real-behavior tests covered the complete reviewer matrix before any
production edit:

```text
$ PYTHONPATH=lib python3 -m unittest <five closure tests>
Ran 5 tests in 1.317s
FAILED (failures=13)

FD ownership: first root descriptor leaked when the second acquisition failed
Typed transforms: path/model/tool sentence replacements were accepted
Dependencies: architect, blast-radius, figure-it-out,
              principle-prove-it-works, and teach remained bundled for Codex
Frontmatter: empty/comment/null/boolean/single-empty descriptions and
             `name: KING MODE` were accepted
Adapter discovery: a symlinked external adapter declaration was admitted
```

The adapter test also contains a deterministic in-tree declaration-directory
swap. The FD test audits first-root, early catalog-validation, and fourth-open
(second identity-check acquisition) exits and closes any leaked test descriptor
before reporting failure.

### Categorical fixes

- `load_catalog` owns the first root FD immediately. If the upstream root open
  fails, it closes the first root; otherwise a nested `finally` closes both on
  every validation/error/return path. Second identity-check descriptors use
  nullable ownership and close safely when either acquisition fails.
- Adapter discovery is fully descriptor-relative beneath the held root. It
  holds and identity-revalidates `adapters/`, each declaration directory,
  `adapter.json`, and referenced JSON. Symlinked directories and deterministic
  directory swaps fail closed. Declarations are validated in memory without a
  pathname reopen or provider import.
- Typed model/tool/path/host declarations now validate structural token
  grammars. Models and tools are bounded identifiers; paths contain path syntax
  and no whitespace/control characters; hosts use explicit source identities
  and bounded host targets. A sentence or paragraph cannot masquerade as an
  allowed replacement, so independent parity cannot bless arbitrary body
  destruction.
- Frontmatter accepts the observed corpus only: 52 sources have the exact
  catalog stable ID and pstack's one legacy display identity is explicitly
  declared as `frontmatter_name: "Poteto Mode"`. Description forms are exactly
  39 nonempty double-quoted strings, 12 nonempty plain strings, and 2 nonempty
  folded `>-` blocks. Empty, comment-only, null, boolean, collection,
  single-empty, malformed, control-containing, ambiguous, and all-caps alias
  inputs fail.
- Catalog dependency edges are explicit and validated:

```text
architect -> how, why, arena, interrogate
blast-radius -> how, why, arena
figure-it-out -> poteto-mode, show-me-your-work, architect
principle-prove-it-works -> show-me-your-work
teach -> how, why
```

Codex unsupported status therefore closes transitively over the graph. Codex
ownership no longer claims those five dependent skill directories.

### GREEN and final evidence

```text
$ PYTHONPATH=lib python3 -m unittest <five closure tests>
Ran 5 tests in 0.891s
OK

$ PYTHONPATH=lib python3 -m unittest tests.test_skills
Ran 23 tests in 9.436s
OK

$ PYTHONPATH=lib python3 -m unittest discover -s tests -q
Ran 107 tests in 16.745s
OK
```

Pure CLI/accounting evidence:

```text
pstack check: revision=63d938c status=clean; claude parity=[]; codex parity=[]
claude sync:   skills=65 files=130 bundled=53 plugin-managed=12 unsupported=0
claude render: skills=65 files=131 bundled=53 plugin-managed=12 unsupported=0
codex sync:    skills=65 files=40  bundled=36 plugin-managed=11 unsupported=18
codex render:  skills=65 files=41  bundled=36 plugin-managed=11 unsupported=18
direct semantic parity: claude=() codex=()
```

Static and native evidence:

```text
py_compile: clean
catalog/transform/adapter JSON: clean
Path.resolve/os.walk/.staging boundary scan: clean
git diff --check: clean
protected five hashes: exact baseline matches
~/.claude, ~/.codex, ~/.kingstack: real directories
all five checked current links: absent
```

No native file, live skill, link, release, schedule, activation, Superpowers
setting, plan, or handoff document was changed. No push occurred in this Task 4
implementer session.

### Standalone final Task 4 reviewer commands

Run from the repository root against the closure commit:

```bash
PYTHONPATH=lib python3 -m unittest tests.test_skills -v
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack sync-upstream pstack --check
./scripts/kingstack sync-upstream pstack --adapter claude --bundle-manifest
./scripts/kingstack sync-upstream pstack --adapter codex --bundle-manifest
./scripts/kingstack render --adapter claude --manifest
./scripts/kingstack render --adapter codex --manifest
git diff 07cd989..HEAD --check
git diff 07cd989..HEAD -- adapters/codex/adapter.json core/skills/catalog.json lib/kingstack/skills.py tests/test_skills.py
git status --short --branch
```

Independently replay the three FD failure stages, paragraph-as-path/model/tool
declarations, the exact 53-source frontmatter corpus plus invalid scalar table,
the five dependency closures, and symlink/swap adapter discovery. Review must
remain read-only. Task 5 and every live/cutover action remain out of scope.
