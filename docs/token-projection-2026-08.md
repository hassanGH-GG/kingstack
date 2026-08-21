# Token projection: the enforcement stack vs the last two months

Written 2026-08-19, the day context enforcement went live. This file exists so the next
review compares reality against numbers fixed in advance, not against memory.

## What actually happened (measured)

Jul 1 to Aug 18, both profiles, list-price equivalent: **~$10,500**, ~12,000 turns,
average context per turn **~430k** (Jul ~447k, Aug ~431k). 98 to 99 percent of all spend
was cache re-reads of conversation history. Source: `usage-ledger.csv` and the Jul/Aug
transcript rollups.

## The counterfactual (modeled)

Same work replayed under the stack: **~$2,300, 78 percent lower.** Lever isolation on the
30-day ledger window (actual $10,915):

| Lever | Alone saves | Mechanism |
|---|---|---|
| 200k context ceiling | ~$7,450 | `autoCompactWindow: 200000`; harness-enforced |
| Polling to zero-LLM | ~$450 | Monitor/hooks instead of turns; measured poll share 4.1% of typed prompts (a floor; agent-side watch loops not counted) |
| Haiku routing of mechanical work | ~$600-700 | routing ruler; assumed 30% of premium tokens were mechanical |

Model assumptions, challengeable: ceiling-era average ctx/turn 140k (ramp to 200k,
compact to ~30k, repeat); linear cost scaling with ctx/turn (true for cache reads);
output quality unchanged at 140k, defensible only because memory, checkpoints, and
compaction steering now exist.

## Falsifiable predictions (check against `usage-ledger.csv` from 2026-08-19 onward)

1. **No day averages above 250k ctx/turn.** The ceiling makes sustained weight above
   200k nearly impossible; a day over 250k means enforcement is not functioning.
2. **The 7-day average ctx/turn lands at 120k to 180k** once pre-ceiling sessions age
   out (allow a few days of mixed data).
3. **Cost per turn falls roughly in proportion** to the ctx/turn drop; if ctx/turn
   halves and cost per turn does not, the model missed something worth finding.
4. **No repeat of a credit-exhaustion mid-task failure** attributable to weight
   (Fable's death on 2026-08-18 was the trigger incident).

If prediction 2 lands near 250k instead of 140k, the likely cause is sessions that
legitimately need deep context (long builds); the answer is more `/clear` discipline
between tasks, not a lower ceiling. If it lands near 140k, the 78 percent figure was
approximately right and this document closes.

## Where the verdict comes from

The `usage-watch` sweep tests prediction 1 daily. `usage-summary.md` carries the trend
for predictions 2 and 3. Review date in `docs/ROADMAP.md`: **2026-08-26**, one week of
clean post-enforcement data.
