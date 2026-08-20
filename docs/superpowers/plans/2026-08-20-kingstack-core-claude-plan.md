# Kingstack Portable Core and Claude Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extract portable instructions, routing, skills, and lifecycle behavior into kingstack while producing a staged Claude adapter that is behaviorally identical to the current live setup.

**Architecture:** Shared source lives under `core/`; adapter declarations describe native filenames, model mappings, and event payload normalization. A deterministic renderer produces a complete adapter under `.staging/claude`. Existing Claude files remain live and unchanged throughout this plan.

**Tech Stack:** Python 3 standard library, Markdown, JSON, POSIX shell, Claude Code hooks, pstack sync scripts.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Work only from `~/Desktop/Work/kingstack`, after the foundation plan is approved.
- Preserve the current `CLAUDE.md` meaning and all 65 baseline skill names.
- Pstack stays upstream-owned; never hand-edit rendered pstack skills.
- Render only to `.staging/claude`; do not write into `~/.claude` in this phase.
- An intentional transformation requires a named rule and a focused test. Silent normalization is a parity failure.

---

### Task 1: Split shared guidance into ordered, deterministic fragments

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
- Create: `tests/test_instruction_render.py`
- Create: `tests/fixtures/claude-baseline/CLAUDE.md`

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

- [ ] **Step 5: Run tests and compare the live file**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_instruction_render -v
./scripts/kingstack render --adapter claude --output .staging/claude
cmp .staging/claude/CLAUDE.md "$HOME/.claude/CLAUDE.md"
```

Expected: tests pass and `cmp` exits 0.

- [ ] **Step 6: Commit**

```bash
git add core/instructions adapters/claude/instructions-appendix.md adapters/codex/instructions-appendix.md lib/kingstack/render.py tests
git commit -m "refactor: extract portable instruction core"
```

### Task 2: Replace vendor model names in policy with portable capability tiers

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
./scripts/kingstack render --adapter claude --output .staging/claude
./scripts/kingstack render --adapter codex --output .staging/codex
! rg -i 'gpt-5\.6-(sol|terra|luna)' .staging/claude
! rg -i '\b(haiku|sonnet|opus|fable)\b' .staging/codex
```

Explicit cross-agent documentation is excluded from generated guidance.

- [ ] **Step 5: Commit**

```bash
git add core/routing adapters/claude adapters/codex lib/kingstack/routing.py tests/test_routing.py core/instructions
git commit -m "feat: route work through portable capability tiers"
```

### Task 3: Make the skill catalog single-source and pstack-safe

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
kingstack sync-upstream pstack --adapter claude --staging DIR
kingstack sync-upstream pstack --adapter codex --staging DIR
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
./scripts/kingstack render --adapter claude --output .staging/claude
test "$(find .staging/claude/skills -name SKILL.md | wc -l | tr -d ' ')" -ge 65
```

- [ ] **Step 5: Commit**

```bash
git add core/skills lib/kingstack/skills.py scripts/sync-pstack.sh tests/test_skills.py
git commit -m "refactor: make skills and pstack adapter-neutral"
```

### Task 4: Normalize lifecycle events behind portable hook commands

**Files:**

- Create: `core/hooks/events.py`
- Create: `core/hooks/session_start.py`
- Create: `core/hooks/stop_capture.py`
- Create: `core/hooks/pre_compact.py`
- Create: `core/hooks/post_tool_use.py`
- Create: `core/hooks/subagent_start.py`
- Create: `adapters/claude/hooks/normalize.py`
- Create: `tests/test_hook_contracts.py`
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

- [ ] **Step 5: Render and syntax-check the full staged Claude adapter**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_hook_contracts -v
./scripts/kingstack render --adapter claude --output .staging/claude
find .staging/claude/hooks -name '*.sh' -exec bash -n {} +
find .staging/claude -name '*.py' -exec python3 -m py_compile {} +
jq -e . .staging/claude/settings.json >/dev/null
```

- [ ] **Step 6: Commit**

```bash
git add core/hooks adapters/claude/hooks lib/kingstack/render.py tests/test_hook_contracts.py
git commit -m "refactor: normalize kingstack lifecycle hooks"
```

### Task 5: Prove staged Claude parity against the frozen baseline

**Files:**

- Create: `lib/kingstack/parity.py`
- Create: `tests/test_claude_parity.py`
- Create: `docs/migration/claude-staged-parity.md`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write a failing parity test with one intentional mismatch**

The report must fail on a missing skill, hook event, schedule, agent, command,
policy section, pstack revision, mode bit, or unmanaged hash change. It reports
all mismatches in one run.

- [ ] **Step 2: Implement `kingstack check --staged --adapter claude`**

Compare the foundation manifest with staged output using capability IDs rather
than file counts alone. Required IDs include all 65 skills, two pstack agents,
five lifecycle events, 16 helper commands, three schedules, four sweeps, 200k
compaction, medium main effort, pstack revision, king-mode, memory-review, and
the current global instruction sections.

- [ ] **Step 3: Run full static and replay verification**

```bash
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack render --adapter claude --output .staging/claude
./scripts/kingstack check --staged --adapter claude
"$HOME/.claude/scripts/check-setup.sh"
git status --short
```

Expected: staged parity green; live Claude still `SETUP HEALTHY`; live baseline
hashes unchanged.

- [ ] **Step 4: Record evidence and commit; do not install**

The report lists each capability ID before/after and any approved filename-only
transform. Commit:

```bash
git add lib/kingstack/parity.py lib/kingstack/cli.py tests/test_claude_parity.py docs/migration/claude-staged-parity.md
git commit -m "test: prove staged Claude adapter parity"
```

- [ ] **Step 5: Stop for Hassan's phase review**

Do not write into `~/.claude`. The live install happens only after shared-memory
and Codex staging are both available for cross-agent tests.
