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

Three agent virtues (Lauren's, adapted): **Laziness**, spend effort once so the bot
does it forever after ("how can an agent do this instead of me?"). **Impatience**,
instead of asking "should we do this?", build it with the agent and share the PR.
**Hubris**, own the outcome fully even when the agent's hands made it.

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

# Constraints live in the code

The best rules are types, folders, and compiler errors. A markdown line is for
what the compiler cannot say. Refactor the tree and pick a stack with real
diagnostics before writing another skill. Files have a place. This kind of
code goes there. If the weakest agent can still drop a file in the wrong
layer, the architecture is unfinished.

# Delete, then simplify, then speed, then automate

Question the requirement first, especially if a smart person wrote it. Then
delete the part or the process. If nothing ever comes back, you are not
deleting enough. Simplify only after delete. Speed up only after simplify.
Automate last. Do not skip to a hook, a skill, or a script while the extra
file is still there.

# You are the gardener

A smell that shows up twice is a design defect, not a chat note. The third
`isRecord` this week, a lint suppression, a helper that should have been a
type. Pull it, then encode the constraint in the repo so it cannot grow
back. Without that job the checkout is just whatever landed.

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

Lauren Tan's pstack (adapted from cursor/plugins) is the process framework.
Bundled skills come from the kingstack catalog, not from editing
`~/.claude/skills/` by hand.

**Default-on.** For any non-trivial task (bug, feature, refactor, investigation,
migration, anything past a quick question or one-line edit), invoke `poteto-mode`
first unasked and let it pick the playbook and skills; never hand-sequence them.
Restate the goal as a checkable finish condition, deriving one if the request has
none. Skip only for trivial lookups, pure conversation, or when Hassan says to
work outside it.

Model roles live in `~/Desktop/Work/kingstack/pstack-models.md`. Superpowers
stays enabled until Hassan disables it after cutover. One front door is still
pstack.

**Absorbing pstack whole, kept current.** The install is a scripted port of the
upstream checkout at `~/Desktop/Work/plugins/pstack`, never a hand-edited fork.
`~/Desktop/Work/kingstack/scripts/sync-pstack.sh` pulls upstream and re-applies
every adapter transform; run it whenever Lauren ships. Last synced commit is in
`~/Desktop/Work/kingstack/pstack-upstream.txt`. Never edit a pstack skill in
place; the next sync overwrites it. Anything of Hassan's goes in `king-mode`
or in this file. Her guide is the manual: `plugins/pstack/docs/guide/`.
Stack iteration is a standing thread: ideas live in
`~/Desktop/Work/kingstack/docs/ROADMAP.md`. When Hassan shares an idea for the
stack in any session, append it to Ideas (dated). A "stack session" starts by
reading that file.
`~/Desktop/Work/kingstack/scripts/kingstack setup` prepares `~/.kingstack`
and never writes a native home. `~/Desktop/Work/kingstack/scripts/kingstack check --all --mode staged` verifies
the checkout. Live health stays unhealthy until a native home is linked.
`~/Desktop/Work/kingstack/scripts/kingstack effort --file` scans spawn lines.
`~/Desktop/Work/kingstack/scripts/kingstack handoff --finish` writes a Codex
packet. `~/Desktop/Work/kingstack/scripts/kingstack session list` shows the
working-set index. CI runs unit tests and staged health.
`~/Desktop/Work/kingstack/scripts/usage-report.py` reports token usage from
transcripts. A nightly launchd job (`com.hassan.claude-usage-snapshot`, 00:23)
rolls each day into the usage ledger. Transcripts expire in about 30 days.

# Model and effort routing

The shared routing policy classifies work by portable capability tier. The main
thread model remains user-controlled at effort medium, set once by the user. Every
subagent sets its adapter model and effort explicitly, reports both to the parent
or user, and starts with the cheapest suitable tier (mechanical → economical,
precise → balanced, judgment → frontier). Escalate only on evidence and name the
choice in one clause. If a selected model is unavailable, fall back exactly one
adjacent tier for that spawn, report the reason, and never apply a blanket
override. Polling and waiting are never model turns (monitor, until-loop, or
hook). Bulk over ~200 lines never enters the main thread; an economical-tier
subagent returns a summary. Past ~150k tokens of context, propose the adapter's
fresh-context command. Context and compaction ceilings otherwise remain native
to the adapter. `kingstack effort --file` scans `↳ spawn` lines. Inherit is
fail. Named model and effort pass.

# kingstack is a repo

The canonical checkout is `~/Desktop/Work/kingstack` (public, MIT,
`hassanGH-GG/kingstack`). `~/.claude` is a live Claude home, not the source
repo. An allowlist `.gitignore` tracks only authored files. After any change
to a tracked file in this session, commit it in the checkout
(`git -C ~/Desktop/Work/kingstack add <paths> && git -C ~/Desktop/Work/kingstack commit -m "..."`)
and push when Hassan says. Read `~/Desktop/Work/kingstack/README.md` for the map.
Shared curated memory lives under `~/.kingstack/memory`. Native homes stay
unlinked until Hassan approves `docs/migration/pre-link-briefing.md`.
A teammate follows `docs/SETUP.md`. Checkout is `KINGSTACK_ROOT` or the
clone. `kingstack memory harvest` and `kingstack memory consolidate` write
candidates only. Hassan still promotes. Fat tool text is
`~/.kingstack/headroom`. Retrieve with `kingstack headroom retrieve <id>`.
The working-set index is `~/.kingstack/sessions`. List with
`kingstack session list`. Continue with `kingstack session continue <id>`.
Pointers only. Do not open another host's transcript.

# Document to preserve context

Commit work-in-progress thinking to durable docs (specs, design docs,
CONTEXT.md, docs/ai/*) during the work, not as post-hoc cleanup. Conversations
get compacted; docs persist across sessions and collaborators. Non-obvious
decisions and mid-task discoveries go in immediately.

# Claude model routing

`~/.claude/model-routing.md` is Claude's global routing ruler, injected into every
session. Economical maps to Haiku, balanced maps to Sonnet, and frontier maps to
Opus by default; Fable may replace Opus only through a private availability
override for that spawn. Select the main-thread model once through `/model`, keep
effort medium, and report the chosen model and effort. Past ~150k tokens of
context, propose `/clear`.

Context cost is on the Claude status line via `hooks/ctx-status.py`. The line
shows model, effort, context, and which models subagents used. Same command:
`kingstack status`. `kingstack effort --file` scans `↳ spawn` lines. Inherit
is fail. Shared memory is `~/.kingstack/memory`. The working-set index is
`~/.kingstack/sessions`. Fat tool text is
`~/.kingstack/headroom`. A teammate starts at `docs/SETUP.md`.
