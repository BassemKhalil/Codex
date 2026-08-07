#!/usr/bin/env python3
"""
Edge-candidate comparison (see EDGE_COMPARISON.md for findings).

A. Release-latency: winner-bracket price appreciation by UTC hour vs
   model-release windows.
B. Station-true: lead-2 modal hit rates and replay using forecasts at the
   resolution station (EGLC) vs the city grid point vs the market favorite.

Requires:
  data/polymarket_london.json   (fetch_polymarket.py)
  data/leads_london.csv         (fetch_leads.py)
  data/leads_london_eglc.csv    (fetch_leads.py with EGLC coords 51.5053,0.0553)
"""

import csv
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

DATA = os.path.join(os.path.dirname(__file__), "data")
MODELS = ["ecmwf", "gfs", "icon", "ukmo", "gem", "jma"]
TZ = ZoneInfo("Europe/London")
RELEASE_HOURS = {5, 6, 7, 8, 9, 17, 18, 19, 20, 21}  # post-run windows, UTC


def br(x):
    return math.floor(x + 0.5)


def ncdf(x, mu, s):
    if s <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1 + math.erf((x - mu) / (s * math.sqrt(2))))


def load_leads(path):
    out = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            vals = {m: float(r[m]) for m in MODELS if r[m] not in ("", None)}
            if len(vals) >= 2:
                out[(r["date"], int(r["lead"]))] = vals
    return out


def robust_ens(vals):
    v = list(vals.values())
    if len(v) >= 4:
        kept = [x for m, x in vals.items()
                if abs(x - statistics.median(
                    [y for mm, y in vals.items() if mm != m])) <= 3.0]
        if len(kept) >= 3:
            v = kept
    return statistics.median(v), statistics.pstdev(v)


def candidate_a(events):
    hour_moves = defaultdict(list)
    for ev in events:
        w = [b for b in ev["brackets"] if b["final"] and b["final"] > 0.9]
        if len(w) != 1 or len(w[0]["history"]) < 10:
            continue
        h = w[0]["history"]
        for (t1, p1), (t2, p2) in zip(h, h[1:]):
            if t2 - t1 <= 2 * 3600:
                hour_moves[datetime.fromtimestamp(t2, timezone.utc).hour].append(p2 - p1)
    total = sum(sum(v) for v in hour_moves.values())
    rel = sum(sum(hour_moves.get(h, [])) for h in RELEASE_HOURS)
    print("A. Release-latency: winner appreciation share in release windows: "
          f"{rel / total:.0%} (windows cover {len(RELEASE_HOURS) / 24:.0%} of hours)")
    peak = max(hour_moves, key=lambda h: sum(hour_moves[h]))
    print(f"   Peak discovery hour: {peak:02d}:00 UTC (target-day afternoon obs)")


def candidate_b(events, grid, eglc):
    stats = defaultdict(lambda: defaultdict(int))
    opportunities = []
    for ev in events:
        d = ev["date"]
        w = [b for b in ev["brackets"] if b["final"] and b["final"] > 0.9]
        fg, fe = grid.get((d, 2)), eglc.get((d, 2))
        if len(w) != 1 or not (fg and fe):
            continue
        res = w[0]["temp"]
        mug, _ = robust_ens(fg)
        mue, sde = robust_ens(fe)
        target = date.fromisoformat(d)
        all_ts = sorted({t for b in ev["brackets"] for t, _ in b["history"]})
        ts2 = next((t for t in all_ts
                    if (target - datetime.fromtimestamp(t, TZ).date()).days == 2),
                   None)
        fav = px_modal = None
        if ts2:
            bp = -1
            for b in ev["brackets"]:
                px = None
                for t_, p_ in b["history"]:
                    if t_ <= ts2:
                        px = p_
                    else:
                        break
                if px is None or b["is_upper"] or b["is_lower"]:
                    continue
                if px > bp:
                    bp, fav = px, b["temp"]
                if b["temp"] == br(mue):
                    px_modal = px
        m = d[:7]
        stats[m]["n"] += 1
        stats[m]["grid"] += (br(mug) == res)
        stats[m]["eglc"] += (br(mue) == res)
        stats[m]["mkt"] += (fav == res)
        if px_modal is not None:
            mp = ncdf(br(mue) + 0.5, mue, sde) - ncdf(br(mue) - 0.5, mue, sde)
            opportunities.append((d, px_modal, mp, br(mue) == res))

    print("\nB. Station-true: lead-2 modal hit rates by month")
    tot = defaultdict(int)
    for m in sorted(stats):
        s = stats[m]
        print(f"   {m}: n={s['n']:3d} grid {s['grid']/s['n']:4.0%} "
              f"EGLC {s['eglc']/s['n']:4.0%} market {s['mkt']/s['n']:4.0%}")
        for k in s:
            tot[k] += s[k]
    print(f"   TOTAL n={tot['n']}: grid {tot['grid']/tot['n']:.0%} "
          f"EGLC {tot['eglc']/tot['n']:.0%} market {tot['mkt']/tot['n']:.0%}")

    print("\n   Replay grid (buy EGLC modal at lead-2 open):")
    for label, ceil, evf in [("ceiling .455 + model-EV", 0.455, True),
                             ("no filter", 0.455, False)]:
        n = wins = 0
        pnl = early = late = 0.0
        for d, px, mp, won in opportunities:
            if px < 0.04 or px > ceil or (evf and mp < px):
                continue
            p = 10 * (1 - px) / px if won else -10.0
            n += 1
            wins += won
            pnl += p
            if d[:7] <= "2026-04":
                early += p
            else:
                late += p
        print(f"   {label}: n={n} win={wins/n:.0%} pnl=${pnl:.0f} "
              f"roi={pnl/(10*n):+.1%} (Feb-Apr ${early:.0f} / May-Jul ${late:.0f})")


def main():
    with open(os.path.join(DATA, "polymarket_london.json")) as f:
        events = json.load(f)
    candidate_a(events)
    candidate_b(events,
                load_leads(os.path.join(DATA, "leads_london.csv")),
                load_leads(os.path.join(DATA, "leads_london_eglc.csv")))


if __name__ == "__main__":
    main()
