---
name: kingstack-health
enabled: true
schedule: daily
cwd: ~/Desktop/Work/kingstack
model: haiku
max_turns: 8
report: log
owner: hassan
allow: Bash(./scripts/kingstack check --all --mode staged*), Bash(~/Desktop/Work/kingstack/scripts/kingstack*)
---
You are an unattended sweep. From the kingstack checkout (KINGSTACK_ROOT or
~/Desktop/Work/kingstack), run `./scripts/kingstack check --all --mode staged`
and read its output. If the last line is `healthy`, reply exactly
`OK: staged healthy`. Otherwise reply `ATTENTION:` and the check output.
Do not attempt to fix anything. Do not write a native home.
