# Core Task 2 implementation report

Append-only evidence log.

## Implementation: deterministic shared guidance render

Base: `fa7a2fc`

### Result

- Froze the exact tracked root `CLAUDE.md` at 9,525 bytes and SHA-256
  `7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e`.
  The same digest was already recorded in
  `docs/baselines/claude-codex-baseline.json` and matches live
  `~/.claude/CLAUDE.md`.
- Split the document at existing heading boundaries into all eight ordered
  fragments without rewriting, rewrapping, or normalizing prose. Each fragment
  is UTF-8 and ends with exactly one newline; inter-section blank lines are
  preserved as the leading byte of the following fragment.
- Added deterministic zero-byte Claude and Codex appendices for this phase.
- Added a validated adapter-ID renderer and a CLI staging writer confined to
  `.staging/<adapter>`. It rejects adapter/path symlinks, traversal, malformed
  order files, missing/unlisted/duplicate fragments, invalid UTF-8, wrong
  newline discipline, nonempty output collisions, and existing output files.
- Rendered only `.staging/claude/CLAUDE.md`; no Claude or Codex native path was
  written, linked, renamed, or removed.

### TDD evidence

1. Initial RED:
   `PYTHONPATH=lib python3 -m unittest tests.test_instruction_render -v`
   failed with `ModuleNotFoundError: No module named 'kingstack.render'`.
2. First GREEN: 11/11 focused render tests passed after the minimal renderer.
3. Confinement mutation RED: a real adapter-directory symlink escaped the repo
   and the focused suite failed because `RenderError` was not raised.
4. Confinement GREEN: explicit adapter path-component symlink rejection made
   13/13 focused tests pass.

### Verification evidence

- Focused: `PYTHONPATH=lib python3 -m unittest tests.test_instruction_render -v`
  -> 13/13 passing.
- Full: `PYTHONPATH=lib python3 -m unittest discover -s tests -v`
  -> 71/71 passing.
- CLI: `./scripts/kingstack render --adapter claude --output .staging/claude`
  -> wrote only `.staging/claude/CLAUDE.md`.
- Exact parity:
  `cmp .staging/claude/CLAUDE.md tests/fixtures/claude-baseline/CLAUDE.md` and
  `cmp .staging/claude/CLAUDE.md ~/.claude/CLAUDE.md` both exited 0.
- Collision proof: a second identical CLI render exited nonzero with
  `staged output directory is not empty`; the staged SHA stayed unchanged.
- Native no-change hashes before/after:
  - Claude guidance: `7a6f34e0ff3777279053bb63713dfc109761d508f18fef0316279e9a74fdab2e`
  - Claude settings: `d68a1b364130ec36f9bde97e6926f02040d455b217352e367da6aa5b51c8477b`
  - Codex config: `ef83efb8a9b49180aae027805422ac039888b08bff8671a8c2038ef22cc18b14`
  - `~/.claude` and `~/.codex` remained real directories, not links.
- `python3 -m py_compile` passed for renderer, CLI, and focused tests.
- `python3 -m json.tool` passed for order and both adapter declarations.
- `git diff --check` passed.

### Concerns

None. The Codex appendix intentionally remains empty in Task 2; vendor-neutral
model prose and the first non-identical Codex render belong to Task 3.
