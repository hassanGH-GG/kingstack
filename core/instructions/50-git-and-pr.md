
# Parallel sessions and git safety

Parallel Claude and Cursor sessions share one checkout; uncommitted work has a
short half-life.

- **Commit verified work immediately** once typecheck, lint, and tests pass.
- **`git add <explicit paths>`, not `git add -A`**, or a parallel session's files
  land in the PR. Before pushing, scan the changed-files list for files I never
  touched.
- **Never `git stash`, `git checkout <ref>`, or `git reset` on a shared
  checkout.** Read another branch's file with `git show <ref>:<path>`.
- Forbid subagents on a live working tree from stash, checkout, reset, add,
  commit.

# PR workflow (GitHub projects)

- PRs auto-merge once CI and the Greptile bot are green. A "do not merge" comment
  does not hold past all-green; keep it a draft if it must not land.
- Comment `@greptile review` to trigger it.
- Graphite (`gt`) handles stacked PRs. In a fresh worktree run
  `gt track --parent main` before submitting; `gt submit` creates drafts by default.
