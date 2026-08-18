<EXTREMELY_IMPORTANT>
pstack (poteto-mode) is Hassan's mandatory process framework, tuned by his personal king-mode.

For ANY non-trivial task — a bug, feature, refactor, investigation, migration, or anything beyond a quick lookup or one-line edit — you MUST invoke the Skill tool with skill "poteto-mode" BEFORE any other response or action, then immediately invoke skill "king-mode" (Hassan's own reply-shape, autonomy, and finish-line rules; it layers on poteto-mode). poteto-mode picks the playbook and invokes the other skills itself; never hand-sequence skills.

Before starting work, restate the goal as a checkable finish condition ("done means ..."); if the request has none, derive one and state it.

Skip both only for trivial lookups, pure conversation, or when Hassan explicitly says to work outside them ("skip the mode", "quick and dirty").

Model and effort routing is a global ruler: read ~/.claude/model-routing.md. Two hard rules from it: (1) waiting or polling is never an LLM turn, use Monitor / an until-loop / a hook; (2) anything over ~200 lines the main thread would read goes to a haiku subagent that returns a summary. Choose subagent model and effort per unit of work (mechanical → haiku, precise → sonnet/opus, judgment → fable/opus), never by inheriting the parent, and name the pick in one clause. Skill-prescribed roles come from ~/.claude/pstack-models.md.
</EXTREMELY_IMPORTANT>
