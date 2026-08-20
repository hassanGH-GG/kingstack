
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
