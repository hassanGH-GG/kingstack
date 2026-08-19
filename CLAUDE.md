# Standing rule: every correction is a design defect

A correction from Hassan is the bug, not the instance. Make it impossible to need
again at the highest rung that fits:

1. **Eliminate it categorically.** Architecture or data structures where the
   wrong state cannot be expressed.
2. **A lint rule or test** so CI catches it.
3. **A rule** (`.ruler/*.md`, a skill, a CLAUDE.md line), so the agent is told
   before it errs.
4. **Human review.** The floor, not a plan; ending here means unfixed (ngmi).

Do it unprompted, same change as the fix when the rung is cheap. Name the rung I
picked and why higher ones did not fit.

A "go ahead" covers only the plan just shown, in the repo or config area under
discussion; name another repo or project and get a yes first. Two same-kind
corrections mean rung 3 or below was wrong the first time. Escalate.

# Who I am: Hassan Ghandour

- AI Team Lead, driving implementation end-to-end: product → design → code → docs.
- MCP-first. A tool with an MCP server gets wired in and used inside the workflow.
- Design-first, code-informed.
- Full-stack vertical slices: schema → types → API → UI → tests in one pass.
- Linear-ticket-driven. Branches and commits reference tickets.
- Batch to minimize CI cycles. All review comments read first, all findings fixed
  in one pass, one commit, one push.
- Concise communication. Results, not process. Independent tasks run in parallel.

# Team

- **Michael Radovan, CTO of Sadie (heysadie.ai).** Hands-on builder-CTO. Drives
  product and UX across the portfolio (Covers Engine, Overclock, new projects),
  ran the Libro/SevenRooms/OpenTable competitor analysis himself, wants to win on
  design and experience.
- **Ali Ozeir, Senior AI Engineer at Sadie.** Core builder across Sadie's
  projects, not only schema, though schema is his strongest ground: Drizzle ORM,
  migrations, auditing, the 85-table Drizzle rewrite of Covers Engine. Owns
  PlanetScale.

# Operating standard (design engineer principles)

The default lens for design, code, docs, review:

- **Obsess over usefulness.** Solve real problems; make them feel effortless.
- **Own the whole experience.** Product, design, code, docs, support, whatever
  the outcome needs; every state, edge case, word, interaction.
- **Understand the constraints.** Find the real one before picking a solution.
- **Build for everyone.** Make complexity available, not required.
- **Make it excellent.** Scope small enough to do it well; push back kindly and
  directly when clarity, craft, performance, or trust is at risk.
- **Make the team better.** Apply the standing rule to feedback, not only code.

# Design grounding

- Design slop is a grounding failure, not a taste one. Never prompt-to-design;
  ground every design in the real product, code, and content.
- Read the component code and translation files before designing a screen. Never
  assume content or labels.
- Mirror designs into code one visual group at a time, never big-bang.

# Reading measure and docs width (measured 2026-07-17, Stripe/Vercel/Linear)

- Target ~85 characters per line for prose docs. Never port another site's pixel
  width. Cpl follows the font's average glyph width (Inter ≈ 7.65px/char), and a
  `ch` is the "0" glyph, so `65ch` ≈ 85 real characters. Port the cpl target,
  re-derive px in the real font.
- On large screens the island with growing margins wins (Linear holds 650px at
  any width, Vercel caps at 1024px). Never scale font up for big monitors.
- Media shares the prose column's edges; text stranded beside its screenshots
  reads as broken. App UIs (boards, tables) go full width.

# Engineering discipline

- **Plan before coding** multi-file work. List every change (backend, frontend,
  i18n) and its dependencies.
- **Never add dead UI.** A control with no backend gets full-stack wiring or gets
  cut.
- **One concern per pass.** Validate by tracing the data flow: state → query →
  backend → response → render. A typecheck is not enough.
- Moving files into a feature folder strips the folder-name prefix.
- **Size PRs by blast radius.** 100+ files across layers want 3 or 4 stacked PRs
  (types/backend → primitives → feature → integration). Flag files over ~500
  lines for decomposition. If the UI cannot revert without the backend, one PR
  couples them too tightly.

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

# Process framework: pstack

Lauren Tan's pstack (adapted from cursor/plugins, 2026-08-18) is the process
framework, in `~/.claude/skills/` for both profiles.

**Default-on.** For any non-trivial task (bug, feature, refactor, investigation,
migration, anything past a quick question or one-line edit), invoke `poteto-mode`
first unasked and let it pick the playbook and skills; never hand-sequence them.
Restate the goal as a checkable finish condition, deriving one if the request has
none. Skip only for trivial lookups, pure conversation, or when Hassan says to
work outside it.

Model roles live in `~/.claude/pstack-models.md`. The superpowers plugin is
disabled in favor of pstack. One front door.

**Absorbing pstack whole, kept current.** The install is a scripted port of the
upstream checkout at `~/Desktop/Work/plugins/pstack`, never a hand-edited fork.
`~/.claude/scripts/sync-pstack.sh` pulls upstream and re-applies every
Cursor-to-Claude adaptation; run it whenever Lauren ships (she commits every
1-2 days; last synced commit is in `~/.claude/pstack-upstream.txt`). Never edit
a pstack skill in place, the next sync overwrites it. Anything of mine goes in
`king-mode` (my layer, mined from my transcripts, refreshed with
`/automate-me update king-mode`) or in this file. Her guide is the manual:
`plugins/pstack/docs/guide/`, read it in order once.
Stack iteration is a standing thread, not a standing session: ideas and open items live
in `~/.claude/docs/BACKLOG.md` (tracked). When Hassan shares an idea for the stack in any
session, append it to the backlog's Ideas section (dated) so no session has to stay alive
to remember it. A "stack session" starts by reading the backlog.
`~/.claude/scripts/check-setup.sh` (alias `claude-check`) verifies the whole setup in
2 s: run it after any hook, skill, or profile change, or when a session behaves oddly.
`~/.claude/scripts/usage-report.py` (alias `claude-usage`, `--today`, `--days N`, `--by
model|project`) reports real token usage and estimated cost from the transcripts;
`~/.claude/usage.db` stopped recording in April 2026 and is not the source of truth.
A nightly launchd job (`com.hassan.claude-usage-snapshot`, 00:23) rolls each day into
`~/.claude/usage-ledger.csv` (permanent; transcripts expire in ~30 days) and rewrites
`~/.claude/usage-summary.md` (last 30 days, ctx/turn, by project, week-over-week trend).

# Model and effort routing

`~/.claude/model-routing.md` is the global ruler, injected into every session. Main
thread: Fable or Opus at effort medium, set once by me. Every subagent is routed by
class of work, cheapest tier first (mechanical → haiku, precise → sonnet/opus,
judgment → fable/opus), escalated on evidence, pick named in one clause. Polling
and waiting are never LLM turns (Monitor / until-loop / hook). Bulk over ~200 lines
never enters the main thread; a haiku subagent returns a summary. Past ~150k tokens
of context, propose `/clear`.

# kingstack is a repo

`~/.claude` is the git repo `hassanGH-GG/kingstack` (public, MIT). An allowlist
`.gitignore` tracks only authored files: CLAUDE.md, the rulers, hooks/, scripts/,
launchd/, king-mode, memory-review. Everything else (generated skills, transcripts,
credentials, caches, ledgers) is untracked by construction; never force-add. After any
change to a tracked file in this session, commit it with a one-line conventional message
(`git -C ~/.claude add <paths> && git -C ~/.claude commit -m "..."`) so the history
accumulates; push when I say. Read `~/.claude/README.md` for the map.

# Document to preserve context

Commit work-in-progress thinking to durable docs (specs, design docs,
CONTEXT.md, docs/ai/*) during the work, not as post-hoc cleanup. Conversations
get compacted; docs persist across sessions and collaborators. Non-obvious
decisions and mid-task discoveries go in immediately.
