# Super Saiyan 3 plan

Status: executed on `feat/agent-neutral-kingstack`. No live link. No push.
No Superpowers disablement. No deletion of the six dated plan files.

Done means every structural gap from the 2026-08-21 architecture review is
closed on `feat/agent-neutral-kingstack`, throwaway-home apply and rollback
are proven, staged and live-on-throwaway health both pass, and the pre-link
briefing is the only remaining gate.

This is not a fourth adapter. This is making the existing three trustworthy.

---

## Wave 1. One ownership document

Close the two-list lie.

- Delete the split. `owned-paths.json` becomes the only ownership document.
- `adapter.json` `owned_paths` is generated from it, or removed and read
  through the same loader.
- Schema: `fully_owned`, `mixed`, `forbidden`. Whole-home and `.` stay illegal.
- Render may emit only `fully_owned` plus declared mixed payloads
  (`config-owned.json` counts as a mixed payload, not a live path).
- Activation plans only the same `fully_owned` and `mixed` sets.
- A check fails if render paths, release manifest paths, and ownership
  disagree.

Predicate: `./scripts/kingstack check --all --mode staged` fails if any
adapter's rendered paths are not exactly the ownership document.

## Wave 2. One activate word

- `kingstack release --select --to <id>` retargets private `current`.
- `kingstack release --activate` is deleted.
- `kingstack activate --dry-run` plans a native-home link from a real
  release digest. It loads the release tree. Fake ids fail.
- `kingstack activate` without `--dry-run` still errors on native homes.

Predicate: `activate --release deadbeef --dry-run` exits 2.
`activate --release <real> --dry-run` lists only owned and mixed paths
that exist in that release.

## Wave 3. Real TOML and JSON merge

The hardest live files.

- Replace the line scanner with a real TOML parse and emit.
- Owned keys only. Unowned keys, comments, and ordering of unowned spans
  stay. Inverse patch is a first-class function, not a later idea.
- `settings.json` gets the same treatment as a JSON merge with an owned-key
  set.
- Neither merger runs against a live home in this wave. Tests use fixtures
  that match the real Claude settings and Codex config shapes.

Predicate: fixture tests prove unowned bytes survive apply and rollback.
A conflicting owned key fails closed.

## Wave 4. Throwaway apply and rollback

Write `apply_activation` and `rollback_activation` against a temp home
that is not `~/.claude`, `~/.codex`, or `~/.cursor`.

- Dated siblings for every fully owned path.
- Mixed files go through Wave 3 mergers.
- `fail_after` stays test-only.
- Inject failure after each rename, merge, wrapper publish, and `current`
  switch. Every failure leaves the pre-state or a complete rollback state.
- Idempotent second apply.
- Refuse parent symlinks, occupied rollback destinations, and whole-home
  ownership.

Predicate: `tests/test_activation.py` covers the fault matrix.
`apply_activation` on `Path.home()/".claude"` still raises.

## Wave 5. Memory that stays rejected

- Candidate id hashes adapter, project, and content. Not session.
- Session stays metadata.
- A rejected content hash suppresses re-proposal for that project until
  the body changes.
- Secrets still never appear in logs.
- Port the nine live inbox cases plus cross-adapter promote/reject.
- Dry-run migrate against the real Claude banks. Apply only to a temp
  store, not `~/.kingstack/memory`, until you say so.

Predicate: same fact from two sessions has one id. Reject once, it does
not return. Apply to a fixture store is hash-identical and leaves sources
untouched.

## Wave 6. Neutral core, honest matrix, real health

- Derive `NATIVE_HOMES` from adapter `native_home` declarations.
- Staged checks discover adapters from disk. No `(claude, codex, cursor)`
  literals in core.
- Capability matrix describes harness truth, not task progress. Activation
  and rollback are core capabilities, declared once, same status on all
  three adapters.
- `--rendered` parity compares release or bundle to a frozen baseline, not
  to today's `~/.claude`.
- `live` health on a throwaway home can pass after Wave 4. `live` health
  against a real native home stays unhealthy until you approve a link.
- Schedule JSON uses portable templates (`$KINGSTACK_ROOT`, `$CLAUDE_HOME`)
  and a check diffs them against the tracked plists.
- Skill unsupported lists fail closed. A new `Task` construct targeting
  Codex without a declared unsupported row is an error.
- Render providers read hook bytes through the same descriptor-confined
  loader as instruction fragments.

Predicate: adding a fourth adapter JSON is enough to appear in staged
health and native-home refusal. No core file names the three vendors
except adapter directories themselves.

## Wave 7. Briefing, then stop

Rewrite `docs/migration/pre-link-briefing.md` from the Wave 1 ownership
document and the Wave 4 throwaway evidence.

Stop. Push, Superpowers, six-file deletion, and any real native-home
write wait on your tokens.

---

## Out of scope until after Wave 7

- Live `~/.claude` / `~/.codex` / `~/.cursor` links
- Copy-only apply into the real `~/.kingstack/memory`
- Disabling Superpowers
- Deleting the six dated plan files
- Push or merge
- A fourth adapter
- Rewriting pstack
- A file-by-file restore engine

## What this does not change

Claude, Codex, and Cursor stay first-party adapters. Codex still records
the 18 Task/loop skills as unsupported. That gap is honesty, not a defect.
Cursor still does not get Cloudflare plugins it does not have.
