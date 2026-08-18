#!/usr/bin/env python3
"""rework-report: how often does the agent need correcting?

The honest proxy for whether the framework is working. Cost and turn counts say how much
you spent; this says how much of it was spent going back over the same ground. It counts
correction-shaped prompts (the human pushing back, repeating, or challenging) as a share
of all typed prompts, per week and per project.

  rework-report.py                    # last 60 days, by week
  rework-report.py --by project
  rework-report.py --samples          # show what actually matched, so the number is auditable
  rework-report.py --snapshot         # append to the permanent ledger (transcripts expire)

This is a PROXY, not truth. A challenge ("why not in parallel?") is not always rework, and
a silent redo is missed entirely. Read the trend, not the absolute value, and use --samples
whenever a number looks wrong.
"""
import json, os, re, sys, glob, csv, argparse
from collections import defaultdict
from datetime import datetime, timedelta

PROJ = os.path.expanduser("~/.claude/projects")
LEDGER = os.path.expanduser("~/.claude/rework-ledger.csv")
FIELDS = ["week", "project", "prompts", "rework", "negation", "repeat", "unfixed", "challenge", "escalation"]

HUMAN_SOURCES = {"typed", "suggestion_accepted"}
PREAMBLE = re.compile(r"^(?:you are (?:a|an|the|working|running)\b|your (?:job|task) is\b|act as\b)", re.I)

# Each pattern is a distinct way the human signals "that was not right". They are applied
# ONLY to the human's own words, never to pasted material: Hassan's long prompts are a paste
# plus one line of instruction, and scoring the paste produced almost all false positives
# (a pasted CV with a name in caps read as escalation; a pasted table read as negation).
PATTERNS = {
    "negation":   re.compile(r"^(?:no|nope|nah|wrong|stop)\b|\b(?:that'?s wrong|not what i (?:said|asked|meant)|instead of that|revert that)\b", re.I),
    "repeat":     re.compile(r"\b(?:i said|like i said|as i said|i already (?:said|told)|i told you)\b|\bagain\s*[!?.]*$", re.I),
    "unfixed":    re.compile(r"\bstill\s+(?:not|no|doesn'?t|didn'?t|broken|failing|there|the same)\b|\b(?:doesn'?t|didn'?t)\s+(?:work|feel|look|seem)\b|\bnot fixed\b|\bsame (?:issue|error|problem)\b|\bno change\b", re.I),
    "challenge":  re.compile(r"\bwhy (?:did|are|is|was|we|not|do|would)\b|\bshouldn'?t (?:it|we|this)\b", re.I),
    "escalation": re.compile(r"!!|\bresearch well\b|\bplease please\b", re.I),
}

# Claude Code surfaces its own failures as user-role rows; they are not prompts.
SYSTEM_NOISE = re.compile(
    r"^(?:can'?t reach the server|api error|request interrupted|\[request interrupted"
    r"|no response requested|caveat: the messages below)", re.I)

# A pasted block, not something a person typed at the prompt.
PASTE_LINE = re.compile(r"^\s*(?:[-*|>#`]|\d+[.)]\s|\w+\s*[:=]\s*[{\[\"']|https?://)")

def own_words(text):
    """The human's own instruction, with pasted material stripped.

    A long prompt is almost always a paste plus one line. Keep the first line that reads like
    a person talking, and cap it: a correction is short, and anything past ~300 characters is
    material rather than instruction.
    """
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    if not lines:
        return ""
    spoken = [l for l in lines[:3] if not PASTE_LINE.match(l)]
    if not spoken:
        return ""
    line = spoken[0]
    # An ALL-CAPS shout is escalation only when the person is shouting, not when a pasted
    # heading happens to be capitalised, so it is judged on a short own-words line only.
    if len(line) <= 120 and len(re.findall(r"\b[A-Z]{3,}\b", line)) >= 2:
        line += " !!"
    return line[:300]

def human_prompts(path):
    """Yield (timestamp, text) for prompts a person actually typed in this session."""
    try:
        with open(path, errors="ignore") as fh:
            for line in fh:
                if '"type":"user"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except Exception:
                    continue
                if r.get("type") != "user" or r.get("promptSource") not in HUMAN_SOURCES:
                    continue
                msg = r.get("message") or {}
                content = msg.get("content")
                texts = [content] if isinstance(content, str) else [
                    b.get("text", "") for b in content or [] if isinstance(b, dict) and b.get("type") == "text"
                ]
                for t in texts:
                    t = (t or "").strip()
                    if (not t or t.startswith("<") or "command-name" in t
                            or PREAMBLE.match(t) or SYSTEM_NOISE.match(t)):
                        continue
                    yield r.get("timestamp", ""), t
    except OSError:
        return

def classify(text):
    return [name for name, rx in PATTERNS.items() if rx.search(text)]

def collect(days):
    since = datetime.now().astimezone() - timedelta(days=days)
    rows, samples = [], []
    # A continued or forked session copies earlier turns verbatim into a new transcript, so
    # the same prompt appears in more than one file. Count each one once.
    seen = set()
    for f in glob.glob(f"{PROJ}/*/*.jsonl"):
        if datetime.fromtimestamp(os.path.getmtime(f)).astimezone() < since:
            continue
        project = os.path.basename(os.path.dirname(f)).strip("-").split("-")[-1]
        for ts, text in human_prompts(f):
            if not ts:
                continue
            when = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone()
            if when < since:
                continue
            fingerprint = (when.isoformat(timespec="seconds"), text[:120])
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            hits = classify(own_words(text))
            rows.append((when, project, hits))
            if hits:
                samples.append((when, project, hits, text[:110].replace("\n", " ")))
    return rows, samples

def week_of(dt):
    return (dt - timedelta(days=dt.weekday())).strftime("%Y-%m-%d")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=60)
    ap.add_argument("--by", choices=["week", "project"], default="week")
    ap.add_argument("--samples", action="store_true")
    ap.add_argument("--snapshot", action="store_true")
    a = ap.parse_args()

    rows, samples = collect(a.days)
    if not rows:
        print("no typed prompts in range")
        return

    agg = defaultdict(lambda: defaultdict(int))
    for when, project, hits in rows:
        key = week_of(when) if a.by == "week" else project
        agg[key]["prompts"] += 1
        if hits:
            agg[key]["rework"] += 1
        for h in hits:
            agg[key][h] += 1

    if a.snapshot:
        existing = []
        if os.path.exists(LEDGER):
            with open(LEDGER) as fh:
                existing = [r for r in csv.DictReader(fh)]
        byweek = defaultdict(lambda: defaultdict(int))
        for when, project, hits in rows:
            k = (week_of(when), project)
            byweek[k]["prompts"] += 1
            if hits:
                byweek[k]["rework"] += 1
            for h in hits:
                byweek[k][h] += 1
        touched = {k for k in byweek}
        keep = [r for r in existing if (r["week"], r["project"]) not in touched]
        for (w, p), c in byweek.items():
            keep.append({"week": w, "project": p, "prompts": c["prompts"], "rework": c["rework"],
                         **{n: c[n] for n in ("negation", "repeat", "unfixed", "challenge", "escalation")}})
        keep.sort(key=lambda r: (r["week"], r["project"]))
        with open(LEDGER, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(keep)
        print(f"rework ledger updated: {len(keep)} rows -> {LEDGER}")

    label = "week starting" if a.by == "week" else "project"
    print(f"{label:<16} {'prompts':>8} {'rework':>7} {'per 10':>7}   negation repeat unfixed challenge escalation")
    tot = defaultdict(int)
    for k in sorted(agg, reverse=(a.by == "week")):
        c = agg[k]
        for n, v in c.items():
            tot[n] += v
        rate = c["rework"] / c["prompts"] * 10
        print(f"{k:<16} {c['prompts']:>8} {c['rework']:>7} {rate:>7.1f}   "
              f"{c['negation']:>8} {c['repeat']:>6} {c['unfixed']:>7} {c['challenge']:>9} {c['escalation']:>10}")
    rate = tot["rework"] / tot["prompts"] * 10
    print(f"{'TOTAL':<16} {tot['prompts']:>8} {tot['rework']:>7} {rate:>7.1f}")
    print(f"\n{rate:.1f} of every 10 typed prompts is correction-shaped. Lower is better. "
          f"Proxy only: run with --samples to audit what matched.")

    if a.samples:
        print("\nmatched prompts (most recent 25):")
        for when, project, hits, text in sorted(samples, reverse=True)[:25]:
            print(f"  {when:%m-%d %H:%M} {project:<12} {','.join(hits):<28} {text}")

if __name__ == "__main__":
    main()
