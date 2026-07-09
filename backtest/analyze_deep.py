#!/usr/bin/env python3
"""Deep-dive diagnostics on backtest results: per-city/side breakdowns,
robustness to outliers, staleness artifacts, and full-threshold skill."""

import json
import os
import statistics
from collections import defaultdict

DATA = os.path.join(os.path.dirname(__file__), "data")
r = json.load(open(os.path.join(DATA, "results.json")))


def breakdown(cfg_label):
    combined = next(c for c in r["combined"] if c["label"] == cfg_label)
    trades = combined["trades"]
    out = {"label": cfg_label, "n": len(trades), "pnl": combined["total_pnl"]}

    by = defaultdict(lambda: {"n": 0, "pnl": 0.0, "wins": 0})
    for t in trades:
        for key in (("city", t["city"]), ("side", t["side"]),
                    ("month", t["date"][:7]),
                    ("entry_band", "cheap<0.15" if t["entry"] < 0.15 else
                     "mid" if t["entry"] < 0.5 else "fav>=0.5")):
            k = f"{key[0]}:{key[1]}"
            by[k]["n"] += 1
            by[k]["pnl"] += t["pnl"]
            by[k]["wins"] += t["won"]
    out["breakdown"] = {k: {"n": v["n"], "pnl": round(v["pnl"], 1),
                            "win_rate": round(v["wins"] / v["n"], 2)}
                        for k, v in sorted(by.items())}

    pnls = sorted((t["pnl"] for t in trades), reverse=True)
    out["top5_winners_pnl"] = round(sum(pnls[:5]), 1)
    out["pnl_without_top5"] = round(sum(pnls[5:]), 1)
    out["pnl_without_top10"] = round(sum(pnls[10:]), 1)
    return out


report = {}
for label in ["LIVE CONFIG (as deployed)", "sigma x2.0",
              "sigma x2+floor1.8, edge 0.25", "decide 09:00 same day"]:
    report[label] = breakdown(label)

print(json.dumps(report, indent=1))
