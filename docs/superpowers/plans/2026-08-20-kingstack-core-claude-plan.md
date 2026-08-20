# Kingstack Adapter Contract, Portable Core, and Claude Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Define a reusable agent-adapter contract, extract portable instructions, routing, skills, and lifecycle behavior into kingstack, and produce a pure rendered Claude bundle that is behaviorally identical to the current live setup.

**Architecture:** Shared source lives under `core/`; a behavioral contract defines guidance, skills, lifecycle intents, routing, memory, scheduling, ownership, release, and rollback capabilities without naming a harness. Adapter declarations map that contract to native files and payloads and publish explicit capability matrices. A deterministic renderer is a pure function returning an ordered mapping of relative path to bytes. It never publishes a mutable staging tree. The later release builder materializes that bundle directly into a uniquely named immutable private release. Existing Claude files remain live and unchanged throughout this plan.

**Tech Stack:** Python 3 standard library, Markdown, JSON, POSIX shell, Claude Code hooks, pstack sync scripts.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Work only from `~/Desktop/Work/kingstack`, after the foundation plan is approved.
- Preserve the current `CLAUDE.md` meaning and all 65 baseline skill names.
- Pstack stays upstream-owned; never hand-edit rendered pstack skills.
- Render only in memory; filesystem materialization belongs exclusively to the immutable release builder. Do not write into `~/.claude` in this phase.
- An intentional transformation requires a named rule and a focused test. Silent normalization is a parity failure.
- A synthetic third adapter fixture must satisfy the contract without importing Claude or Codex implementation modules.
- Capability status is exactly one of `native`, `emulated`, `degraded`, or `unsupported`; every non-native status requires evidence and strict-parity impact.

---

### Task 1: Define the adapter contract and capability matrix

**Files:**

- Create: `adapters/contract/adapter.schema.json`
- Create: `adapters/contract/capability.schema.json`
- Create: `core/capabilities/catalog.json`
- Create: `adapters/claude/adapter.json`
- Create: `adapters/codex/adapter.json`
- Create: `tests/fixtures/adapters/example/adapter.json`
- Create: `tests/fixtures/adapters/example/capabilities.json`
- Create: `lib/kingstack/adapter_contract.py`
- Create: `tests/test_adapter_contract.py`
- Modify: `lib/kingstack/cli.py`

**Interfaces:**

- Produces: `load_adapter(path: Path) -> AdapterDeclaration`, `validate_adapter(declaration: AdapterDeclaration, catalog: CapabilityCatalog) -> List[str]`, and `compare_capabilities(required: Set[str], matrix: CapabilityMatrix) -> CapabilityReport`.
- Consumed by: every renderer, rendered-parity check, release manifest, installer, rollback command, and future adapter.

- [ ] **Step 1: Write failing contract tests**

```python
class AdapterContractTest(TestCase):
    def test_synthetic_adapter_has_no_first_party_dependency(self):
        adapter = load_adapter(FIXTURES / "adapters/example/adapter.json")
        self.assertEqual(validate_adapter(adapter, catalog()), [])
        self.assertNotIn("claude", adapter.render_module)
        self.assertNotIn("codex", adapter.render_module)

    def test_unsupported_capability_is_visible(self):
        report = compare_capabilities({"before_compaction"}, example_matrix())
        self.assertEqual(report.unsupported, {"before_compaction"})
        self.assertFalse(report.strict_parity)
```

- [ ] **Step 2: Run and confirm the missing contract module**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v`

Expected: import failure for `kingstack.adapter_contract`.

- [ ] **Step 3: Implement schemas, typed declarations, and validation**

The capability catalog assigns stable IDs to guidance, skills, hooks, memory,
routing, schedules, health, activation, and rollback. An adapter declaration
contains `id`, `contract_version`, `render_module`, `native_home`, `owned_paths`,
`model_tiers`, and `capability_matrix`. Reject unknown keys, duplicate owned
paths, absolute owned paths, home-root ownership, missing evidence for non-native
status, and a model tier not mapped by the adapter.

```python
@dataclass(frozen=True)
class CapabilityState:
    capability: str
    status: str
    evidence: str
    strict_parity: bool
```

- [ ] **Step 4: Add and run the contract command**

```bash
./scripts/kingstack check --contract --adapter claude
./scripts/kingstack check --contract --adapter codex
./scripts/kingstack check --contract --adapter-path tests/fixtures/adapters/example
PYTHONPATH=lib python3 -m unittest tests.test_adapter_contract -v
```

Expected: all three declarations validate; the example proves the extension
point without loading either first-party adapter.

- [ ] **Step 5: Commit**

```bash
git add adapters/contract adapters/claude/adapter.json adapters/codex/adapter.json core/capabilities lib/kingstack/adapter_contract.py lib/kingstack/cli.py tests/test_adapter_contract.py tests/fixtures/adapters
git commit -m "feat: define the agent adapter contract"
```

### Task 2: Split shared guidance into ordered, deterministic fragments

**Files:**

- Create: `core/instructions/order.json`
- Create: `core/instructions/00-identity.md`
- Create: `core/instructions/10-correction-rule.md`
- Create: `core/instructions/20-operating-standard.md`
- Create: `core/instructions/30-engineering-discipline.md`
- Create: `core/instructions/40-model-and-context.md`
- Create: `core/instructions/50-git-and-pr.md`
- Create: `core/instructions/60-memory-and-docs.md`
- Create: `core/instructions/70-stack-iteration.md`
- Create: `adapters/claude/instructions-appendix.md`
- Create: `adapters/codex/instructions-appendix.md`
- Create: `lib/kingstack/render.py`
- Create: `lib/kingstack/adapters/claude.py`
- Create: `lib/kingstack/adapters/codex.py`
- Create: `tests/fixtures/adapters/example/sample_agent/render.py`
- Create: `tests/test_instruction_render.py`
- Create: `tests/fixtures/claude-baseline/CLAUDE.md`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Freeze the current guidance as the golden fixture**

Copy the exact tracked `CLAUDE.md` into the fixture using `apply_patch`, not a
shell redirect. Record its SHA-256 in the foundation baseline.

- [ ] **Step 2: Write failing render tests**

```python
class InstructionRenderTest(TestCase):
    def test_claude_render_is_byte_identical_to_baseline(self):
        actual = render_instructions("claude", ROOT)
        expected = (FIXTURES / "claude-baseline/CLAUDE.md").read_text()
        self.assertEqual(actual, expected)

    def test_order_lists_every_fragment_once(self):
        order = json.loads((ROOT / "core/instructions/order.json").read_text())
        self.assertEqual(len(order), len(set(order)))
        self.assertEqual(set(order), {p.name for p in (ROOT / "core/instructions").glob("*.md")})
```

- [ ] **Step 3: Run and confirm failure**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_instruction_render -v`

- [ ] **Step 4: Extract by existing heading boundaries without rewriting prose**

`order.json` is an array of filenames. `render_instructions()` reads them in
that order, verifies UTF-8 and one trailing newline, concatenates without adding
a generated banner, then appends only the target appendix. The Claude appendix
starts empty so the first render is byte-identical.

```python
def render_instructions(adapter: str, root: Path) -> str:
    order = json.loads((root / "core/instructions/order.json").read_text())
    body = "".join(_read_fragment(root, name) for name in order)
    appendix = root / "adapters" / adapter / "instructions-appendix.md"
    return body + appendix.read_text()
```

`render_bundle(adapter, root)` loads the validated declaration's
`render_module`, imports that provider, and calls its
`render(root, declaration, shared_sources)` function. A provider returns a
mapping of portable relative path to bytes. The core canonicalizes and validates
every path, requires deterministic sorted keys, rejects duplicates and
non-bytes, and requires every output to be covered by `owned_paths`. It returns
an immutable ordered mapping and performs no filesystem write.

The Claude and Codex providers decide their native guidance filename; the core
contains no hardcoded first-party filename map. The synthetic example provider
renders `GUIDANCE.md` through its declared non-first-party module, proving future
adapters need no core change.

The CLI has three mutually exclusive read-only selectors:

- `--manifest` prints schema-versioned path, size, and SHA-256 rows.
- `--print-file PATH` emits exactly one rendered file to stdout and rejects
  unknown or noncanonical paths.
- `--check-file PATH --equals FILE` byte-compares one rendered entry to an
  existing file and writes nothing.

Delete `write_staged_instructions`, remove `render --output`, and delete every
mutable staging publication test. Add tests that the symbol is absent,
`--output` exits 2, all selectors cause zero filesystem writes, and no
production code references `.staging`.

- [ ] **Step 5: Run tests and compare the live file**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_instruction_render -v
./scripts/kingstack render --adapter claude --check-file CLAUDE.md --equals "$HOME/.claude/CLAUDE.md"
./scripts/kingstack render --adapter claude --manifest | jq -e '.files[0].path == "CLAUDE.md"'
```

Expected: tests and the byte comparison pass with no filesystem publication.

- [ ] **Step 6: Commit**

```bash
git add core/instructions adapters/claude/instructions-appendix.md adapters/codex/instructions-appendix.md lib/kingstack/render.py lib/kingstack/adapters/claude.py lib/kingstack/adapters/codex.py lib/kingstack/cli.py tests/test_instruction_render.py tests/fixtures/claude-baseline tests/fixtures/adapters/example/sample_agent
git commit -m "refactor: extract portable instruction core"
```

### Task 3: Replace vendor model names in policy with portable capability tiers

**Files:**

- Create: `core/routing/policy.json`
- Create: `adapters/claude/models.json`
- Create: `adapters/codex/models.json`
- Create: `lib/kingstack/routing.py`
- Create: `tests/test_routing.py`
- Modify: `core/instructions/40-model-and-context.md`
- Modify: `adapters/claude/instructions-appendix.md`

- [ ] **Step 1: Write failing mapping and fallback tests**

```python
self.assertEqual(resolve("claude", "mechanical")["model"], "haiku")
self.assertEqual(resolve("codex", "mechanical")["model"], "gpt-5.6-luna")
self.assertEqual(resolve("codex", "precise")["effort"], "medium")
self.assertEqual(fallback("codex", "frontier"), "balanced")
self.assertRaises(RoutingError, resolve, "codex", "unknown")
```

- [ ] **Step 2: Define the portable policy and adapter maps**

`policy.json` contains only:

```json
{
  "waiting": {"tier": "none", "effort": "none"},
  "mechanical": {"tier": "economical", "effort": "low"},
  "precise": {"tier": "balanced", "effort": "medium"},
  "judgment": {"tier": "frontier", "effort": "high"}
}
```

Claude maps economical/balanced/frontier to available Haiku/Sonnet/Opus-or-
Fable choices. Codex maps them to Luna/Terra/Sol. Availability overrides live
in private runtime state, never in the shared policy. `fallback()` moves exactly
one adjacent tier and returns the chosen tier and reason.

- [ ] **Step 3: Make shared prose vendor-neutral**

Move Claude-specific model names and `/model` details into the Claude appendix.
The shared fragment says every spawn sets model and effort explicitly, reports
both, and falls back one adjacent tier on an availability error.

- [ ] **Step 4: Prove both rendered policies have no foreign model names**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_routing -v
! ./scripts/kingstack render --adapter claude --print-file CLAUDE.md | rg -i 'gpt-5\.6-(sol|terra|luna)'
! ./scripts/kingstack render --adapter codex --print-file AGENTS.md | rg -i '\b(haiku|sonnet|opus|fable)\b'
```

Explicit cross-agent documentation is excluded from generated guidance.

- [ ] **Step 5: Commit**

```bash
git add core/routing adapters/claude adapters/codex lib/kingstack/routing.py tests/test_routing.py core/instructions
git commit -m "feat: route work through portable capability tiers"
```

### Task 4: Make the skill catalog single-source and pstack-safe

**Files:**

- Create: `core/skills/catalog.json`
- Move: `skills/king-mode/` -> `core/skills/authored/king-mode/`
- Move: `skills/memory-review/` -> `core/skills/authored/memory-review/`
- Create: `core/skills/transforms/claude.json`
- Create: `core/skills/transforms/codex.json`
- Create: `lib/kingstack/skills.py`
- Create: `tests/test_skills.py`
- Modify: `scripts/sync-pstack.sh`

- [ ] **Step 1: Write failing catalog tests against the 65-name baseline**

```python
catalog = load_catalog(ROOT)
self.assertEqual(set(catalog.available_names("claude")), set(BASELINE_65_NAMES))
self.assertEqual(catalog.upstream_revision("pstack"), "63d938c")
self.assertEqual(catalog.owner("king-mode"), "kingstack")
self.assertEqual(catalog.owner("cloudflare"), "plugin-manager")
```

Also test duplicate names, missing `SKILL.md`, invalid frontmatter, unknown owner,
and a hand-edited generated pstack output.

- [ ] **Step 2: Build the catalog schema**

Each entry has: `name`, `owner` (`kingstack`, `pstack`, `adopted`, or
`plugin-manager`), `source`, `targets`, `dependencies`, and optional
`transform`. Plugin-managed skills are recorded for parity but not copied.

- [ ] **Step 3: Refactor pstack sync behind one target-aware entry point**

```text
kingstack sync-upstream pstack --adapter claude --bundle-manifest
kingstack sync-upstream pstack --adapter codex --bundle-manifest
kingstack sync-upstream pstack --check
```

Retain the existing clobber manifest behavior. Transform only documented host
terms, then fail if a forbidden host term remains. Never overwrite an authored
skill or a generated file whose installed hash differs from its manifest.

- [ ] **Step 4: Render both catalogs and verify meaning preservation**

For every portable skill compare normalized headings, instruction paragraphs,
referenced resource names, and script hashes between source and target. Adapter
changes may affect frontmatter/model/tool/path tokens only.

```bash
PYTHONPATH=lib python3 -m unittest tests.test_skills -v
./scripts/kingstack sync-upstream pstack --check
./scripts/kingstack render --adapter claude --manifest | jq -e '[.files[].path | select(startswith("skills/") and endswith("/SKILL.md"))] | length >= 65'
```

- [ ] **Step 5: Commit**

```bash
git add core/skills lib/kingstack/skills.py scripts/sync-pstack.sh tests/test_skills.py
git commit -m "refactor: make skills and pstack adapter-neutral"
```

### Task 5: Normalize lifecycle events behind portable hook commands

**Files:**

- Create: `core/hooks/events.py`
- Create: `core/hooks/session_start.py`
- Create: `core/hooks/stop_capture.py`
- Create: `core/hooks/pre_compact.py`
- Create: `core/hooks/post_tool_use.py`
- Create: `core/hooks/subagent_start.py`
- Create: `adapters/claude/hooks/normalize.py`
- Create: `tests/test_hook_contracts.py`
- Create: `tests/test_rendered_bundle_syntax.py`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write one golden input/output case for each existing event**

The normalized envelope is:

```python
{
  "event": "SubagentStart",
  "agent": "claude",
  "session_id": "session-123",
  "project": "/absolute/cwd",
  "payload": {"role": "builder", "model": "sonnet", "effort": "medium", "task": "render the adapter"}
}
```

Golden outputs reproduce current semantics: SessionStart contract and pending
memory count; Stop candidate capture; PreCompact checkpoint plus preserve
directive; PostToolUse warning above the current threshold; SubagentStart model,
effort, role, and task visibility.

- [ ] **Step 2: Run tests and observe missing modules**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_hook_contracts -v`

- [ ] **Step 3: Port logic without changing thresholds or policy**

Keep hook business logic pure: `handle(event: dict, runtime: Path) -> dict`.
Only the adapter normalizer knows Claude's native payload keys. Shell wrappers
resolve the neutral checkout, read stdin once, and exec the Python handler.

- [ ] **Step 4: Replay captured Claude fixtures through old and new hooks**

For each event compare exit code, JSON fields, system message, candidate hash,
and checkpoint contents with timestamps normalized. Add a test that malformed
input exits safely and never blocks Stop.

- [ ] **Step 5: Render and syntax-check the full Claude bundle without publication**

`tests/test_rendered_bundle_syntax.py` validates bundle bytes directly without
materializing them: shell entries parse with `bash -n` through stdin, Python
entries compile from bytes, JSON entries parse, TOML patch declarations satisfy
the constrained patch schema, Markdown skill frontmatter is valid, and every
bundle path is canonical and covered by adapter ownership.

```bash
PYTHONPATH=lib python3 -m unittest tests.test_hook_contracts -v
./scripts/kingstack render --adapter claude --manifest | jq -e '.files | length > 0'
PYTHONPATH=lib python3 -m unittest tests.test_rendered_bundle_syntax -v
```

- [ ] **Step 6: Commit**

```bash
git add core/hooks adapters/claude/hooks lib/kingstack/render.py tests/test_hook_contracts.py tests/test_rendered_bundle_syntax.py
git commit -m "refactor: normalize kingstack lifecycle hooks"
```

### Task 6: Prove rendered Claude parity against the frozen baseline

**Files:**

- Create: `lib/kingstack/parity.py`
- Create: `tests/test_claude_parity.py`
- Create: `docs/migration/claude-rendered-parity.md`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write a failing parity test with one intentional mismatch**

The report must fail on a missing skill, hook event, schedule, agent, command,
policy section, pstack revision, mode bit, or unmanaged hash change. It reports
all mismatches in one run.

- [ ] **Step 2: Implement `kingstack check --rendered --adapter claude`**

Compare the foundation manifest with the in-memory rendered bundle using capability IDs rather
than file counts alone. Required IDs include all 65 skills, two pstack agents,
five lifecycle events, 16 helper commands, three schedules, four sweeps, 200k
compaction, medium main effort, pstack revision, king-mode, memory-review, and
the current global instruction sections.

- [ ] **Step 3: Run full static and replay verification**

```bash
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack render --adapter claude --manifest | jq -e '.files | length > 0'
./scripts/kingstack check --rendered --adapter claude
"$HOME/.claude/scripts/check-setup.sh"
git status --short
```

Expected: rendered parity green; the two previously documented live Claude
health drifts remain unchanged; live baseline
hashes unchanged.

- [ ] **Step 4: Record evidence and commit; do not install**

The report lists each capability ID before/after and any approved filename-only
transform. Commit:

```bash
git add lib/kingstack/parity.py lib/kingstack/cli.py tests/test_claude_parity.py docs/migration/claude-rendered-parity.md
git commit -m "test: prove rendered Claude adapter parity"
```

- [ ] **Step 5: Record the gate and continue only with pure bundles**

Independent review must approve the report. Do not write into `~/.claude`. The
mandatory Hassan review occurs only after shared-memory and Codex bundle/release proof are
both available and immediately before any live link.
