# Kingstack Shared Curated Memory Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copy the seven curated Claude memory banks into one private, agent-neutral store and let any contract-compliant adapter capture, review, reject, and recall approved memory without merging native automatic memory systems.

**Architecture:** Shared memory lives under `~/.kingstack/memory` with an append-safe inbox, stable candidate IDs, per-project approved banks, and a rejection ledger. Adapter hooks normalize arbitrary adapter provenance into the same versioned schema; Claude and Codex are initial fixtures, not an enum. Migration is copy-only and hash-verified; original Claude banks remain untouched.

**Tech Stack:** Python 3 standard library, Markdown with YAML-like frontmatter, JSON Lines, SHA-256, file locking via atomic rename and advisory directory locks.

**Spec:** `docs/superpowers/specs/2026-08-20-agent-neutral-kingstack-design.md`

## Global Constraints

- Never merge or relocate any adapter's raw transcripts, native memory databases, caches, or automatic memory stores.
- Only approved curated facts cross agents.
- Existing memory filenames, bodies, frontmatter, timestamps, and indexes are copied byte-for-byte before any schema evolution.
- A candidate is never promoted automatically. `memory-review` remains the human gate.
- Secrets are rejected on capture and promotion; secret-like content never appears in logs or error messages.
- Original Claude banks remain readable and unchanged through final acceptance.

---

### Task 1: Define project identity and the shared memory layout

**Files:**

- Create: `core/memory/schema.json`
- Create: `lib/kingstack/project_id.py`
- Create: `lib/kingstack/memory_store.py`
- Create: `tests/test_project_id.py`
- Create: `tests/test_memory_store.py`

- [ ] **Step 1: Write failing project-identity tests**

Cover a normal Git checkout, worktree, symlinked path, non-Git directory, and
two paths with the same basename. With a remote, the stable identity is the
normalized remote URL; without a remote, it is the Git common-directory
identity so a main checkout and its worktrees match. Only non-Git directories
fall back to a resolved absolute-path hash. Checkout roots and human labels are
metadata, never identity.

```python
self.assertEqual(project_id(main), project_id(worktree))
self.assertNotEqual(project_id(Path("/a/foo")), project_id(Path("/b/foo")))
self.assertRegex(project_id(repo), r"^p_[0-9a-f]{16}$")
```

- [ ] **Step 2: Write failing store-layout tests**

Expected private layout:

```text
~/.kingstack/memory/
  projects.json
  inbox.jsonl
  reviews.jsonl
  projects/<project-id>/
    MEMORY.md
    memories/*.md
    manifest.json
```

Assert directory mode `0700`, file mode `0600`, deterministic project registry,
and refusal when the root resolves inside the public repository.

- [ ] **Step 3: Implement the exact store interfaces**

Define `ProjectIdentity(id, label, root, remote_fingerprint)` as a frozen
dataclass. `MemoryStore` exposes `open(root)`, `register_project(identity)`,
`bank(project_id)`, `append_candidate(candidate)`, and
`review(candidate_id, verdict, actor, memory=None)`. Use Python 3.9-compatible
`typing.Optional` annotations.

Writes use a lock directory created with `mkdir`; stale locks include PID and
timestamp and are never removed automatically while the PID is alive. JSONL
appends are written to a sibling temporary file, `fsync`ed, then atomically
renamed. Every public method validates schema version `1`.

- [ ] **Step 4: Run focused tests**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_project_id tests.test_memory_store -v
```

- [ ] **Step 5: Commit**

```bash
git add core/memory lib/kingstack/project_id.py lib/kingstack/memory_store.py tests/test_project_id.py tests/test_memory_store.py
git commit -m "feat: define private shared memory store"
```

### Task 2: Normalize candidate provenance and deduplication

**Files:**

- Create: `lib/kingstack/memory_candidate.py`
- Create: `lib/kingstack/secret_filter.py`
- Create: `tests/test_memory_candidate.py`
- Create: `tests/test_secret_filter.py`
- Create: `tests/fixtures/memory/candidate-claude.json`
- Create: `tests/fixtures/memory/candidate-codex.json`
- Create: `tests/fixtures/memory/candidate-example-adapter.json`

- [ ] **Step 1: Write failing cross-agent identity tests**

All three fixtures carry the same proposed fact with different native session IDs.
Assert their candidate IDs differ when provenance differs, while their content
hashes match. Repeated capture of the same source/session/content returns the
same stable candidate ID and creates no duplicate inbox row.

- [ ] **Step 2: Define the versioned candidate record**

```json
{
  "schema": 1,
  "id": "c_<sha256-prefix>",
  "source_adapter": "<validated adapter contract id>",
  "source_profile": "<adapter-native profile label or unknown>",
  "project_id": "p_<hash>",
  "session_id_hash": "<sha256>",
  "captured_at": "RFC3339 UTC",
  "type": "user|feedback|project|reference",
  "prompt_provenance": "typed|suggestion_accepted|unknown",
  "content_hash": "<sha256>",
  "title": "Use explicit staged paths",
  "description": "Never sweep unrelated work into a shared checkout commit.",
  "body": "Stage only paths owned by the current task."
}
```

Native session identifiers are hashed before persistence. The ID hashes the
canonical JSON of adapter/profile/project/session/content. The adapter ID must
resolve through the adapter contract registry; it is not a Claude/Codex enum.
Timestamps do not participate in the ID.

- [ ] **Step 3: Implement two-stage secret rejection**

The filter checks known token prefixes, assignment-shaped secrets, URLs with
credentials, private-key blocks, and high-entropy values. It returns category
names and redacted locations, never matched values. Add allowlist tests proving
that variable names such as `POSTHOG_KEY` do not become false positives—the
failure already observed in the existing stack.

- [ ] **Step 4: Run focused tests including concurrency**

Spawn 20 local processes appending the same and distinct candidates. Assert the
JSONL remains valid, one duplicate row exists, and no write is lost.

Run: `PYTHONPATH=lib python3 -m unittest tests.test_memory_candidate tests.test_secret_filter -v`

- [ ] **Step 5: Commit**

```bash
git add lib/kingstack/memory_candidate.py lib/kingstack/secret_filter.py tests/test_memory_candidate.py tests/test_secret_filter.py tests/fixtures/memory
git commit -m "feat: normalize and protect memory candidates"
```

### Task 3: Copy the seven Claude banks with a byte-for-byte parity manifest

**Files:**

- Create: `lib/kingstack/memory_migrate.py`
- Create: `tests/test_memory_migrate.py`
- Modify: `lib/kingstack/cli.py`

- [ ] **Step 1: Write failing copy-only migration tests**

Fixture banks include `MEMORY.md`, multiple memory files, Unicode, empty banks,
and an orphan file. Assert:

```python
self.assertEqual(source_hashes, destination_hashes)
self.assertEqual(source_mtimes, destination_original_mtimes)
self.assertTrue(all(original.exists() for original in source_files))
self.assertIn("orphan.md", report["unindexed_files"])
```

Migration refuses a destination containing a different file at the same path
and resumes safely after an interrupted copy.

- [ ] **Step 2: Implement dry-run and apply commands**

```text
kingstack memory migrate-claude --dry-run
kingstack memory migrate-claude --apply --expected-source-manifest <manifest-id>
kingstack memory verify-migration
```

The mapper reads each `~/.claude/projects/*/memory` directory, derives the
project identity, copies files with `copy2` to a temporary bank, writes a
manifest containing original relative path/hash/mode/mtime/provenance, verifies
all bytes, caps destination directories to `0700` and files to `0600` after
recording original modes, then atomically renames the bank into place. It never
follows links or edits the source.

- [ ] **Step 3: Prove the dry-run against the real seven-bank baseline**

Run:

```bash
./scripts/kingstack memory migrate-claude --dry-run
```

Expected: exactly the foundation bank count, every source file classified,
zero overwrites, zero unreadable files, and no writes.

- [ ] **Step 4: Re-inventory, apply to the private store, and prove hashes both ways**

```bash
ks_memory_manifest=$(./scripts/kingstack memory migrate-claude --dry-run --write-private-manifest)
test -n "${ks_memory_manifest:?}"
./scripts/kingstack memory migrate-claude --apply --expected-source-manifest "$ks_memory_manifest"
./scripts/kingstack memory verify-migration
```

Re-run the foundation inventory on the original banks and compare it with the
pre-migration manifest. Expected: all originals unchanged; destination content
hash multiset identical. Apply must abort before writing if the source manifest
does not match the fresh source inventory; no archive is created or required.

- [ ] **Step 5: Commit code and redacted counts only**

Never commit memory content or machine paths. Commit:

```bash
git add lib/kingstack/memory_migrate.py lib/kingstack/cli.py tests/test_memory_migrate.py
git commit -m "feat: migrate curated memory without rewriting sources"
```

### Task 4: Port capture, review, rejection, and index operations

**Files:**

- Create: `core/memory/review.py`
- Create: `core/memory/index.py`
- Create: `tests/test_memory_review.py`
- Modify: `core/hooks/stop_capture.py`
- Modify: `core/skills/authored/memory-review/SKILL.md`

- [ ] **Step 1: Port the nine existing memory tests as an immutable floor**

Copy the behavior cases from `~/.claude/hooks/test_memory_inbox.py` into the new
suite, then add cross-adapter cases: Claude candidate promoted by Codex, Codex
candidate promoted by Claude, a synthetic third-adapter candidate promoted by
Claude, duplicate rejection, secret rejection, and project isolation.

- [ ] **Step 2: Run and ensure the ported suite fails before implementation**

Run: `PYTHONPATH=lib python3 -m unittest tests.test_memory_review -v`

- [ ] **Step 3: Implement the review service**

Expose `list_pending(store, project_id=None)`,
`promote(store, candidate_id, name, memory_type, description, body, actor)`, and
`reject(store, candidate_id, reason, actor)`. Use Python 3.9-compatible `typing`
annotations and return the promoted `Path` from `promote`.

Promotion reruns the secret filter, writes frontmatter plus body to a stable
filename, updates `MEMORY.md` idempotently, and appends a review event. Rejected
content hashes suppress re-proposal for that project unless the content changes.

- [ ] **Step 4: Make memory-review call the shared CLI**

The skill must not contain agent-specific commands. Its examples use:

```text
kingstack memory list
kingstack memory show c_0123456789abcdef
kingstack memory promote c_0123456789abcdef --name explicit-staging --type feedback --description "Stage only task-owned paths"
kingstack memory reject c_fedcba9876543210 --reason "stale project status"
```

- [ ] **Step 5: Run the old and new suites**

```bash
python3 "$HOME/.claude/hooks/test_memory_inbox.py"
PYTHONPATH=lib python3 -m unittest tests.test_memory_review -v
```

Expected: existing nine pass; all new cross-agent cases pass.

- [ ] **Step 6: Commit**

```bash
git add core/memory core/hooks/stop_capture.py core/skills/authored/memory-review tests/test_memory_review.py
git commit -m "feat: share human-reviewed memory across adapters"
```

### Task 5: Add relevant-memory injection through the adapter contract

**Files:**

- Create: `core/memory/context.py`
- Create: `adapters/claude/hooks/session-start-memory.py`
- Create: `adapters/codex/hooks/session-start-memory.py`
- Create: `tests/test_memory_context.py`
- Modify: `core/hooks/session_start.py`
- Modify: `lib/kingstack/render.py`

- [ ] **Step 1: Write failing relevance and bounded-context tests**

Assert a session from Claude, Codex, or the synthetic adapter sees only its
project index, an unrelated project is absent,
the full body is not injected until explicitly recalled, missing banks are
silent, and the index output is capped by a configured byte limit with a pointer
to `kingstack memory recall`.

- [ ] **Step 2: Implement the shared context service**

Expose `session_index(store, cwd, max_bytes=12_000)` and
`recall(store, cwd, names)`, both returning text. Use `typing.List[str]` rather
than Python 3.10 union or built-in generic syntax.

Every native wrapper normalizes `cwd`, invokes the same service, and wraps the
result in its declared hook format. The text names its shared origin and never
claims to be an adapter's native memory. Contract validation refuses an adapter
that claims shared-memory injection without a passing wrapper fixture.

- [ ] **Step 3: Render both staged adapters and replay identical project starts**

```bash
PYTHONPATH=lib python3 -m unittest tests.test_memory_context -v
./scripts/kingstack render --adapter claude --output .staging/claude
./scripts/kingstack render --adapter codex --output .staging/codex
```

Pass equivalent native SessionStart fixtures to both wrappers and compare the
normalized memory section byte-for-byte.

- [ ] **Step 4: Commit**

```bash
git add core/memory/context.py core/hooks/session_start.py adapters/claude/hooks/session-start-memory.py adapters/codex/hooks/session-start-memory.py lib/kingstack/render.py tests/test_memory_context.py
git commit -m "feat: inject bounded shared memory into both agents"
```

### Task 6: Shared-memory acceptance gate

**Files:**

- Create: `docs/migration/shared-memory-verification.md`

- [ ] **Step 1: Run full static, migration, and cross-agent simulations**

```bash
PYTHONPATH=lib python3 -m unittest discover -s tests -v
./scripts/kingstack memory verify-migration
./scripts/kingstack check --staged --adapter claude
./scripts/kingstack check --staged --adapter codex --allow-incomplete-adapter
```

- [ ] **Step 2: Exercise promotion and rejection in an isolated temporary store**

Capture one Claude fixture and one Codex fixture, promote one from the opposite
adapter, reject the other, start both adapter simulations, and prove the
promoted memory appears while the rejected candidate never reappears.

- [ ] **Step 3: Reconfirm no-loss invariants**

Compare all original-bank content hashes, modes, and mtimes to the foundation
manifest. Confirm no file under `~/.kingstack/memory` is tracked by Git and all
private modes are user-only.

- [ ] **Step 4: Record evidence and commit; do not repoint live Claude yet**

```bash
git add docs/migration/shared-memory-verification.md
git commit -m "test: prove shared curated memory without source loss"
```

- [ ] **Step 5: Record the gate and continue only in staging**

Independent review must approve the evidence. Continue to Codex staging with no
live link; Hassan's mandatory review remains immediately before first live
activation.
