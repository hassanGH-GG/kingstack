
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
