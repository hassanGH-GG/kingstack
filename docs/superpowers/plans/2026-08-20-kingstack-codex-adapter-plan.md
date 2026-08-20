# Kingstack Codex Native Adapter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and stage a contract-compliant native Codex adapter that loads kingstack guidance, skills, hooks, shared curated memory, and routing while preserving every pre-existing Codex setting, plugin, MCP server, trusted project, native memory, session, and credential.

**Architecture:** Generate `AGENTS.md`, `hooks.json`, managed skill copies, a capability matrix, and a narrowly owned TOML patch from the shared core into an immutable private release. Test only in isolated temporary Codex homes during this plan. Produce the exact ownership and activation briefing, but create no live Codex link; live activation, native hook trust, rollback, and re-activation occur only in the cutover plan after Hassan's pre-link approval.

**Tech Stack:** Codex CLI/Desktop, AGENTS.md, Codex hooks JSON, Codex skills, TOML, Python 3 standard library, official Codex `/import` comparison.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Never replace `~/.codex/config.toml`; surgically own only reviewed keys and preserve all unrelated bytes and ordering.
- Never touch `auth.json`, sessions, native memories, caches, history, plugin cache, marketplace state, MCP credentials, or notifications.
- Preserve the current main model `gpt-5.6-sol`. Keep main reasoning `high` until the medium-effort behavioral test passes and Hassan approves the change.
- User hook trust is a native Codex security boundary. Do not bypass it for the live acceptance test.
- Do not duplicate a skill already supplied equivalently by an enabled Codex plugin; record the provider and prove semantic parity.
- Disable the Codex `superpowers` plugin only after every required overlapping skill has a verified kingstack/pstack provider; keep its installed source recoverable and prove the before/after capability set is unchanged.
- Official `/import` is a one-time discovery comparison, not the synchronization mechanism.
- Do not create or modify a live path under `~/.codex` in this plan.

---

### Task 1: Render native AGENTS.md and prove shared-policy coverage

**Files:**

- Modify: `adapters/codex/adapter.json`
- Modify: `adapters/codex/instructions-appendix.md`
- Create: `tests/test_codex_instructions.py`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write failing AGENTS.md coverage tests**

Assert the generated file contains every shared policy ID from the instruction
order, Codex-native terms for model/effort, and an appendix that explains the
shared curated memory and neutral repo path. Assert it contains no Claude-only
commands (`/model`, `CLAUDE.md`, Claude hook paths) except a clearly labeled
cross-agent compatibility note.

- [ ] **Step 2: Define Codex adapter metadata**

```json
{
  "id": "codex",
  "contract_version": 1,
  "render_module": "kingstack.adapters.codex",
  "native_home": ".codex",
  "owned_paths": "adapters/codex/owned-paths.json",
  "model_tiers": "adapters/codex/models.json",
  "capability_matrix": "adapters/codex/capabilities.json"
}
```

Guidance, hooks, managed skills, and native-memory support are declared inside
the owned-path and capability documents; they are not extra top-level adapter
keys.

- [ ] **Step 3: Render and validate AGENTS.md**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_codex_instructions -v
./scripts/kingstack render --adapter codex --output .staging/codex
test -s .staging/codex/AGENTS.md
```

- [ ] **Step 4: Commit**

```bash
git add adapters/codex lib/kingstack/render.py tests/test_codex_instructions.py
git commit -m "feat: render native Codex guidance"
```

### Task 2: Build a lossless, narrowly owned Codex TOML merger

**Files:**

- Create: `adapters/codex/config-owned.json`
- Create: `lib/kingstack/toml_patch.py`
- Create: `tests/test_toml_patch.py`
- Create: `tests/fixtures/codex/config-existing.toml`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write failing preservation and conflict tests**

The fixture contains the real structural categories: root model and effort,
plugins, MCP servers, trusted projects, notifications, and comments. Assert the
patch preserves all unrelated byte slices exactly. Add tests for existing
`[agents]`, `[features]`, `[memories]`, duplicate keys, dotted keys, CRLF, and a
conflicting value changed outside kingstack ownership.

```python
self.assertEqual(before_unowned_spans, after_unowned_spans)
self.assertEqual(parsed["agents"]["default_subagent_model"], "gpt-5.6-terra")
self.assertEqual(parsed["agents"]["default_subagent_reasoning_effort"], "medium")
self.assertTrue(parsed["features"]["memories"])
self.assertTrue(parsed["memories"]["disable_on_external_context"])
```

- [ ] **Step 2: Define the only owned keys**

`config-owned.json`:

```json
{
  "agents.default_subagent_model": "gpt-5.6-terra",
  "agents.default_subagent_reasoning_effort": "medium",
  "features.memories": true,
  "memories.generate_memories": true,
  "memories.use_memories": true,
  "memories.disable_on_external_context": true,
  "memories.min_rate_limit_remaining_percent": 35
}
```

Do not own `model` or `model_reasoning_effort` yet.

- [ ] **Step 3: Implement a constrained structural patcher**

Python on this machine lacks `tomllib`, so do not pretend a regex is a general
TOML parser. The patcher recognizes table headers and scalar assignments only
for the owned tables, preserves all other source spans byte-for-byte, refuses
duplicate owned keys, multiline values, arrays-of-tables under owned names, or
syntax it cannot prove safe, and emits an ownership manifest with before/after
hashes.

Expose `patch_codex_config(source, owned)` returning `PatchResult`, and
`verify_unowned_bytes(before, after, result)` raising `PatchError` on drift.
Use Python 3.9-compatible `typing.Dict` annotations.

- [ ] **Step 4: Validate with Codex's real parser, not only unit tests**

Create a temporary `CODEX_HOME`, copy the staged config, and run a read-only
Codex config command such as `codex features list`. Expected: exit 0 with the
patched file. Then insert malformed TOML and prove Codex rejects it and the
installer refuses it.

- [ ] **Step 5: Commit**

```bash
git add adapters/codex/config-owned.json lib/kingstack/toml_patch.py lib/kingstack/render.py tests/test_toml_patch.py tests/fixtures/codex
git commit -m "feat: merge Codex config without clobbering user settings"
```

### Task 3: Generate native Codex hooks and adapters

**Files:**

- Create: `adapters/codex/hooks.json.template`
- Create: `adapters/codex/hooks/normalize.py`
- Create: `adapters/codex/hooks/run.py`
- Create: `tests/test_codex_hooks.py`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write golden native payload tests for five events**

Use official Codex shapes for `SessionStart`, `Stop`, `PreCompact`,
`PostToolUse`, and `SubagentStart`. Assert each normalizes to the core envelope
and each core response maps back to valid Codex hook JSON. Test `Stop` with
`stop_hook_active=true` to prevent loops.

- [ ] **Step 2: Define `hooks.json` with release-selected commands**

Each event has one command handler invoking:

```text
/usr/bin/python3 /Users/mac/.kingstack/adapters/codex/current/hooks/run.py EVENT
```

The path is stable while the `current` selector chooses an immutable release;
no hook executes the mutable canonical checkout. Set short
timeouts, bounded `additionalContextLimit`, no asynchronous behavior for memory
or compaction, and no matcher on `Stop` because Codex ignores it.

- [ ] **Step 3: Implement native normalization**

`normalize.py` maps official fields without assuming Claude names. The
SubagentStart output is visibly:

```text
spawn [ROLE] TASK · model=MODEL effort=EFFORT
```

Missing model or effort is reported as `inherit` plus a warning; visibility is
mechanical, while the spawn remains allowed.

- [ ] **Step 4: Validate schemas and replay the full suite**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_codex_hooks -v
./scripts/kingstack render --adapter codex --output .staging/codex
jq -e . .staging/codex/hooks.json >/dev/null
find .staging/codex/hooks -name '*.py' -exec python3 -m py_compile {} +
```

Run a temporary Codex CLI with `--dangerously-bypass-hook-trust` only inside the
isolated test home, trigger each event, and compare its observable result with
the direct replay. Never use the bypass in the live home.

- [ ] **Step 5: Commit**

```bash
git add adapters/codex/hooks.json.template adapters/codex/hooks lib/kingstack/render.py tests/test_codex_hooks.py
git commit -m "feat: add native Codex lifecycle hooks"
```

### Task 4: Resolve the Codex skill catalog without duplication or loss

**Files:**

- Create: `lib/kingstack/codex_skills.py`
- Create: `tests/test_codex_skills.py`
- Create: `docs/migration/codex-skill-providers.md`
- Modify: `core/skills/catalog.json`

- [ ] **Step 1: Inventory enabled plugin and personal skill providers**

Read names and content hashes from `~/.codex/skills`, enabled plugin caches, and
the staged kingstack catalog. Never modify caches. Generate rows:

```text
skill | required source | existing provider | semantic match | action
```

- [ ] **Step 2: Write failing resolution tests**

Resolver rules:

1. Reuse an enabled plugin skill only when normalized workflow content matches.
2. Install a kingstack-managed copy when absent.
3. Fail on same-name/different-meaning collisions.
4. Never overwrite an unknown personal skill.

Test the current superpowers overlap explicitly. The plugin is not disabled
merely to make the count look clean. Hassan has authorized disabling it at
cutover, but only after the resolver proves every required overlapping
capability has an equivalent kingstack/pstack provider.

- [ ] **Step 3: Implement the provider resolver and managed manifest**

Expose `resolve_codex_skills(catalog, installed)` returning a `Resolution` with
`reuse`, `install`, and `conflict` lists.

The result lists `reuse`, `install`, and `conflict`; conflicts block install.
Installed copies go through staging and carry source hashes in the private
installation manifest.

- [ ] **Step 4: Prove all 65 baseline capabilities are available**

The acceptance check uses capability names and provider records, not simply
`find ~/.codex/skills`. Start an isolated Codex session and ask it to list or
invoke representative pstack, king-mode, memory-review, design, verification,
and adopted skills.

- [ ] **Step 5: Stage the superpowers disable and prove no capability loss**

In an isolated Codex home, capture the discovered capability/provider set with
the plugin enabled, disable only its enabled-state entry, install the resolved
kingstack providers, start a fresh session, and compare capability IDs. Any
missing or semantically different skill blocks the disable. The plugin files and
cache remain installed for rollback.

- [ ] **Step 6: Commit**

```bash
git add lib/kingstack/codex_skills.py tests/test_codex_skills.py core/skills/catalog.json docs/migration/codex-skill-providers.md
git commit -m "feat: resolve Codex skill providers without duplication"
```

### Task 5: Build a versioned Codex release and manifest-owned activation plan

**Files:**

- Create: `lib/kingstack/release.py`
- Create: `lib/kingstack/activation.py`
- Create: `tests/test_codex_release.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write failing immutable-release and ownership tests**

In a fake Codex home and private adapter store, test: deterministic release ID;
exclusive immutable publication; capability and content manifests; unknown file
refusal; user-modified managed path refusal; duplicate ownership refusal;
home-root ownership refusal; config conflict; release verification; activation
dry-run; and byte-identical preservation plans for existing owned paths. Auth,
session, plugin, MCP, notification, and native-memory sentinels remain outside
the plan in every case.

For the mixed `config.toml` surface, inject failure after original rename and
merged-file publication; cover dated-sibling collision, occupied rollback
destination, parent-symlink refusal, fsync ordering, idempotent second apply,
and inverse rollback after adding an unrelated native key. The unrelated key
must survive while owned keys return to their prior projection.

- [ ] **Step 2: Implement immutable release generation**

Expose these Python 3.9-compatible interfaces:

```python
def build_release(adapter_id: str, staged: Path, store: Path,
                  source_hash: str) -> ReleaseManifest: ...
def verify_release(release: Path) -> List[str]: ...
def plan_activation(adapter: AdapterDeclaration, release: ReleaseManifest,
                    native_home: Path, activation_id: str) -> ActivationPlan: ...
```

The release manifest includes contract and generator versions, source hash,
capability matrix, every content hash, and owned-path mapping. Publish to
`~/.kingstack/adapters/codex/releases/<source-hash>` only after verification.
The activation plan is read-only and contains only `AGENTS.md`, the reviewed
hook surface, managed skill entries, and owned TOML edits. It names the exact
unique dated sibling and stable `current`-release target for every path.
Originals remain beside their native paths and are never copied into a
recursive backup tree.

- [ ] **Step 3: Run all fake-home and release tests**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_codex_release -v`

- [ ] **Step 4: Build the real private release and produce a no-write activation diff**

```bash
./scripts/kingstack render --adapter codex --output .staging/codex
ks_codex_release=$(./scripts/kingstack release build --adapter codex --staged .staging/codex --print-id)
test -n "${ks_codex_release:?}"
./scripts/kingstack release verify --adapter codex --release "$ks_codex_release"
./scripts/kingstack activate --adapter codex --release "$ks_codex_release" --dry-run
```

The report must state that current model, main effort, plugins, MCP servers,
trusted projects, notifications, auth, sessions, and native memories remain
unchanged. The command must write only the private immutable release and private
manifest; it must not create `~/.codex` links.

- [ ] **Step 5: Commit the release mechanism; do not activate**

```bash
git add lib/kingstack/release.py lib/kingstack/activation.py lib/kingstack/cli.py tests/test_codex_release.py
git commit -m "feat: stage versioned Codex adapter releases"
```

### Task 6: Prove Codex behavior in isolation and prepare the pre-link briefing

**Files:**

- Create: `docs/migration/codex-staged-verification.md`

- [ ] **Step 1: Materialize an isolated Codex home from the release**

```bash
ks_test_home=$(mktemp -d)
test -n "${ks_test_home:?}"
./scripts/kingstack activate --adapter codex --release "$ks_codex_release" --home "$ks_test_home" --apply
```

- [ ] **Step 2: Exercise native hook trust only inside the isolated home**

Start a fresh Codex CLI with the isolated home, inspect the generated hook
source and hashes, and prove Codex exposes the native trust decision. Record the
exact live hashes that will require Hassan's approval later; do not edit the real
trust store.

- [ ] **Step 3: Run the ten behavioral checks in fresh CLI and desktop sessions**

Using the isolated home, prove: global AGENTS instructions; king-mode/pstack activation; explicit
subagent model and effort visibility; bulk warning; compaction checkpoint;
shared candidate capture; cross-agent promotion; rejection suppression;
scheduled-health compatibility; release verification green. The unified
`kingstack check --adapter codex` command is implemented and exercised later in
the cutover plan, so this phase must not claim it yet.

Use disposable test project content and remove only that test content after its
hashes are recorded. Do not manufacture success by calling hook scripts
directly—the final evidence must come from real Codex events.

- [ ] **Step 4: Exercise isolated rollback and re-activation**

```bash
ks_manifest_id=$(./scripts/kingstack activate latest-manifest --adapter codex --home "$ks_test_home")
test -n "${ks_manifest_id:?}"
./scripts/kingstack rollback --manifest "$ks_manifest_id" --home "$ks_test_home" --dry-run
./scripts/kingstack rollback --manifest "$ks_manifest_id" --home "$ks_test_home" --apply
```

Compare all fake pre-existing managed paths with their dated originals; start
Codex and prove its prior setup works. Then re-activate the versioned release and
rerun the compact smoke suite. No path under the real `~/.codex` may change.

- [ ] **Step 5: Test medium main effort without silently changing the default**

Run matched representative tasks in isolated sessions at high and medium,
measuring completion, corrections, tests, context, and cost. Record the result.
Change the owned key to medium only if parity holds and Hassan approves; else
leave high and record the exception.

- [ ] **Step 6: Run official Claude import as comparison only**

In the isolated Codex CLI use `/import`, select Claude Code, and review the detected
items. Do not enable automatic sync. Export only a redacted capability checklist
to the verification document. Reconcile any supported capability absent from
the generated adapter; do not make imported output canonical.

- [ ] **Step 7: Verify no real-home change and commit staged evidence**

Compare before/after hashes and structural reports for the real Codex home,
including auth sentinels, sessions,
native memories, plugin catalog, MCP config, trusted projects, and notifications.
Run all tests and both adapter checks. Then:

```bash
git add docs/migration/codex-staged-verification.md
git commit -m "test: prove staged Codex adapter and rollback"
```

- [ ] **Step 8: Feed exact owned paths, capability gaps, release ID, and rollback commands into the mandatory pre-link briefing**

Do not activate the live Codex adapter. The cutover plan combines this evidence
with Claude, memory, schedules, documentation, and canonical-clone evidence and
then stops for Hassan's explicit approval.
