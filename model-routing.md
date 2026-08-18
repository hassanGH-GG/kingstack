# Model and effort routing (global ruler)

Cost is decided per unit of work, not inherited from the parent. Before spending
model tokens on anything, classify it and pick the cheapest tier that can succeed.
The main thread cannot change its own model; everything below it can, and must.

## The three layers

1. **Main thread** (this conversation). Fable or Opus, effort medium; the human sets
   it once with `/model` and `/effort`. Its job is judgment: read intent, route,
   evaluate what comes back, decide. Keep bulk out of it (see below).
2. **Subagents and workflows.** `model` and `effort` are per-call. Choose per the
   table. Never pass the parent's model by habit.
3. **Mechanics.** Waiting and watching are not LLM work. `Monitor`, an `until`
   loop, `run_in_background`, or a hook: zero tokens.

## Classify, then route

| Class | Looks like | Route |
|---|---|---|
| Zero-LLM | wait for CI, watch a log, poll a PR or job, "tell me when X" | Monitor / until-loop / hook. No model. |
| Mechanical | grep, read, extract, summarize, count, format, run a script and report its output, bulk file sweeps | `haiku`, effort low |
| Precise execution | a well-specified edit or sequence, apply a codemod, follow a checklist to the letter | `sonnet`, effort medium; `opus` if the diff is large or cross-cutting |
| Judgment | design, ambiguity, review, root cause on a subtle bug, prose people will read, anything worth a second opinion | `fable` or `opus`, effort high |
| Escalation | a lower tier failed, returned INCONCLUSIVE, or produced something you would not ship | one tier up, once; say why in the reply |

Start cheap and escalate on evidence. Do not pre-escalate because the task "seems
important"; importance is a reason to verify, not to overspend.

## Bulk never enters the main thread

Anything over ~200 lines that the main thread would otherwise read (files, logs,
diffs, transcripts, search results) goes to a `haiku` subagent that returns a
summary or a pointer. The main thread re-reads its whole history on every turn, so
one large paste keeps costing for the rest of the session. Route bulk out; keep
conclusions in.

## Session weight

When the conversation is past roughly 150k tokens of context, or when most recent
turns are status checks, say so once and propose `/clear` (memory and `/recall`
make it free). A 400k-token turn costs 4x a 100k one and reasons worse.

## Effort

Effort scales thinking on every turn. Default medium in the main thread. Bump a
subagent to high only for the Judgment class. Never high for polling, routing,
status, or mechanical work.

## Log the pick

When you route work to a subagent, name the class and tier in one clause
("mechanical → haiku"), so the choice is auditable and can be corrected.
Skill-prescribed roles (interrogate reviewers, arena candidates, reflect judges)
keep their prescribed models; this ruler governs everything else.
