<!-- local-edit: runtime-forensics-tui-signal -->

**TUI signal (step 1).** For a terminal UI, the live signal is a PTY capture. Reduce it to four
counts: screen clears, alt-screen entries, bytes written per keystroke, and frames painted per
keystroke under sustained input. Any of them scaling with input is the smoking gun.
