
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
