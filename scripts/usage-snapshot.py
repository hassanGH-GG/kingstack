#!/usr/bin/env python3
"""usage-snapshot: nightly rollup of yesterday's token usage into a durable ledger.

Why: transcripts auto-delete after ~30 days, so without this the history is lost
(May-June 2026 already are). Appends one row per (day, model, project) to
~/.claude/usage-ledger.csv, idempotent (re-running a day replaces its rows), then
rewrites ~/.claude/usage-summary.md with the last 30 days + per-turn context trend.

  usage-snapshot                 # roll up yesterday (default; safe to run any time)
  usage-snapshot --day 2026-08-17
  usage-snapshot --backfill 30   # roll up every day with transcript data, last N days
"""
import json, os, sys, glob, csv, argparse
from collections import defaultdict
from datetime import datetime, timedelta, timezone

PROJ = os.path.expanduser("~/.claude/projects")
LEDGER = os.path.expanduser("~/.claude/usage-ledger.csv")
SUMMARY = os.path.expanduser("~/.claude/usage-summary.md")
FIELDS = ["day", "model", "project", "turns", "fresh_in", "cache_write", "cache_read", "output", "est_cost_usd"]
PRICES = {"fable": (15, 18.75, 1.5, 75), "opus": (15, 18.75, 1.5, 75), "sonnet": (3, 3.75, .3, 15), "haiku": (.8, 1, .08, 4)}
def price(m):
    m = m.lower()
    for k, v in PRICES.items():
        if k in m: return v
    return PRICES["sonnet"]
def project_of(slug): return slug.strip("-").split("-")[-1]

def rollup(day):
    """Return {(model, project): [turns, in, cw, cr, out, cost]} for one local calendar day."""
    start = datetime.strptime(day, "%Y-%m-%d").astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    rows = {}
    for f in glob.glob(f"{PROJ}/*/*.jsonl"):
        if datetime.fromtimestamp(os.path.getmtime(f)).astimezone() < start: continue
        proj = project_of(os.path.basename(os.path.dirname(f)))
        try:
            with open(f, errors="ignore") as fh:
                for line in fh:
                    if '"usage"' not in line: continue
                    try: r = json.loads(line)
                    except: continue
                    if r.get("type") != "assistant": continue
                    m = r.get("message") or {}; u = m.get("usage"); ts = r.get("timestamp")
                    if not u or not ts: continue
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
                    if not (start <= t < end): continue
                    rows[m.get("id") or f + ts] = (m.get("model", "?"), proj, u)
        except OSError: continue
    agg = defaultdict(lambda: [0, 0, 0, 0, 0, 0.0])
    for model, proj, u in rows.values():
        if model.startswith("<"): continue
        p = price(model)
        i, cw, cr, o = (u.get(k, 0) for k in ("input_tokens", "cache_creation_input_tokens", "cache_read_input_tokens", "output_tokens"))
        g = agg[(model, proj)]; g[0] += 1; g[1] += i; g[2] += cw; g[3] += cr; g[4] += o
        g[5] += (i * p[0] + cw * p[1] + cr * p[2] + o * p[3]) / 1e6
    return agg

def load_ledger():
    if not os.path.exists(LEDGER): return []
    with open(LEDGER) as fh: return list(csv.DictReader(fh))

def save_ledger(rows):
    rows.sort(key=lambda r: (r["day"], r["model"], r["project"]))
    tmp = LEDGER + ".tmp"
    with open(tmp, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=FIELDS); w.writeheader(); w.writerows(rows)
    os.replace(tmp, LEDGER)

def upsert_day(day):
    agg = rollup(day)
    rows = [r for r in load_ledger() if r["day"] != day]
    for (model, proj), g in agg.items():
        rows.append({"day": day, "model": model, "project": proj, "turns": g[0], "fresh_in": g[1],
                     "cache_write": g[2], "cache_read": g[3], "output": g[4], "est_cost_usd": f"{g[5]:.2f}"})
    save_ledger(rows)
    return sum(g[0] for g in agg.values()), sum(g[5] for g in agg.values())

def write_summary():
    rows = load_ledger()
    if not rows: return
    by_day = defaultdict(lambda: [0, 0, 0.0])
    by_proj = defaultdict(lambda: [0, 0.0])
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    for r in rows:
        if r["day"] < cutoff: continue
        t = int(r["turns"]); ctx = int(r["fresh_in"]) + int(r["cache_write"]) + int(r["cache_read"]); c = float(r["est_cost_usd"])
        d = by_day[r["day"]]; d[0] += t; d[1] += ctx; d[2] += c
        p = by_proj[r["project"]]; p[0] += t; p[1] += c
    days = sorted(by_day)
    tot_turns = sum(v[0] for v in by_day.values()); tot_cost = sum(v[2] for v in by_day.values())
    lines = [f"# Claude token usage, last 30 days (updated {datetime.now():%Y-%m-%d %H:%M})", "",
             f"**{len(days)} active days · {tot_turns:,} turns · ~${tot_cost:,.0f} list-price equivalent · both profiles combined**", "",
             "Cost here is a list-price estimate for relative comparison; cache reads dominate. Per-turn context is the lever: lighter sessions cost less and think better.", "",
             "| day | turns | ctx/turn | ~cost |", "|---|---|---|---|"]
    for d in reversed(days):
        v = by_day[d]; lines.append(f"| {d} | {v[0]:,} | {v[1]/max(1,v[0])/1e3:.0f}k | ${v[2]:,.0f} |")
    lines += ["", "## By project (30d)", "", "| project | turns | ~cost | share |", "|---|---|---|---|"]
    for p, v in sorted(by_proj.items(), key=lambda kv: -kv[1][1])[:10]:
        lines.append(f"| {p} | {v[0]:,} | ${v[1]:,.0f} | {v[1]/max(1,tot_cost)*100:.0f}% |")
    if len(days) >= 14:
        recent = days[-7:]; prior = days[-14:-7]
        r_ctx = sum(by_day[d][1] for d in recent) / max(1, sum(by_day[d][0] for d in recent))
        p_ctx = sum(by_day[d][1] for d in prior) / max(1, sum(by_day[d][0] for d in prior))
        r_cost = sum(by_day[d][2] for d in recent); p_cost = sum(by_day[d][2] for d in prior)
        lines += ["", "## Trend: last 7 active days vs the 7 before", "",
                  f"- ctx/turn: {p_ctx/1e3:.0f}k → {r_ctx/1e3:.0f}k ({(r_ctx/p_ctx-1)*100:+.0f}%)",
                  f"- cost: ${p_cost:,.0f} → ${r_cost:,.0f} ({(r_cost/max(1,p_cost)-1)*100:+.0f}%)"]
    lines += ["", f"Ledger: `{LEDGER}` (one row per day×model×project, survives transcript expiry). Ad hoc: `claude-usage --today`."]
    with open(SUMMARY, "w") as fh: fh.write("\n".join(lines) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day"); ap.add_argument("--backfill", type=int)
    a = ap.parse_args()
    if a.backfill:
        for i in range(a.backfill, -1, -1):
            d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            t, c = upsert_day(d)
            if t: print(f"{d}: {t} turns, ~${c:,.0f}")
    else:
        d = a.day or (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        t, c = upsert_day(d); print(f"{d}: {t} turns, ~${c:,.0f}")
    write_summary(); print(f"summary → {SUMMARY}")

if __name__ == "__main__": main()
