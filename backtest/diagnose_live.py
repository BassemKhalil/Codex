#!/usr/bin/env python3
"""
Diagnose the live open-window results (July 2026) and evaluate rule fixes.

Faithful replay: walk each market hour-by-hour from open; the bot buys at
the first hour where its rule fires (3h cycle cadence approximated hourly),
using the lead-matched as-issued forecast for that hour.

Variants:
  V0 deployed   price <= hit_rate(city, lead)
  V1 model-EV   V0 AND model_bracket_prob >= price
  V2 robust-sig V0 with outlier-trimmed sigma (model >3C from peer-median dropped)
  V3 best-value candidate brackets modal+-1, buy max(model_p - price) >= 0.05,
                price <= hit_rate
  V4 V1 + V2 + V3 combined
"""

import csv
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

DATA = os.path.join(os.path.dirname(__file__), "data")
MODELS = ["ecmwf", "gfs", "icon", "ukmo", "gem", "jma"]
TZ = ZoneInfo("Europe/London")
HIT = {2: 0.455, 3: 0.40}
STAKE = 10.0


def br(x):
    return math.floor(x + 0.5)


def ncdf(x, mu, s):
    if s <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1 + math.erf((x - mu) / (s * math.sqrt(2))))


def bprob(lo, hi, mu, s):
    return ncdf(hi + 0.5, mu, s) - ncdf(lo - 0.5, mu, s)


def load_leads():
    out = {}
    with open(os.path.join(DATA, "leads_london.csv")) as f:
        for r in csv.DictReader(f):
            vals = {m: float(r[m]) for m in MODELS if r[m] not in ("", None)}
            if len(vals) >= 2:
                out[(r["date"], int(r["lead"]))] = vals
    return out


def ensemble(vals, robust=False):
    v = list(vals.values())
    if robust and len(v) >= 4:
        kept = []
        for m, x in vals.items():
            peers = [y for mm, y in vals.items() if mm != m]
            if abs(x - statistics.median(peers)) <= 3.0:
                kept.append(x)
        if len(kept) >= 3:
            v = kept
    return statistics.median(v), statistics.pstdev(v)


def replay(events, leads, variant, start_date=None, end_date=None):
    trades = []
    for ev in events:
        d = ev["date"]
        if (start_date and d < start_date) or (end_date and d > end_date):
            continue
        winners = [b for b in ev["brackets"] if b["final"] and b["final"] > 0.9]
        if len(winners) != 1:
            continue
        resolved = winners[0]["temp"]
        target = date.fromisoformat(d)

        # hourly union of price timestamps
        all_ts = sorted({t for b in ev["brackets"] for t, _ in b["history"]})
        bought = None
        for ts in all_ts:
            lead = (target - datetime.fromtimestamp(ts, TZ).date()).days
            if lead < 2:
                break
            if lead > 3:
                continue
            f = leads.get((d, min(lead, 7)))
            if not f:
                continue
            mu, sd = ensemble(f, robust=variant in ("V2", "V4"))
            modal = br(mu)

            if variant in ("V3", "V4"):
                cand_temps = [modal - 1, modal, modal + 1]
            else:
                cand_temps = [modal]

            best = None
            for ct in cand_temps:
                cb = next((b for b in ev["brackets"]
                           if not b["is_upper"] and not b["is_lower"]
                           and b.get("temp_low", b["temp"]) <= ct <= b["temp"]), None)
                if cb is None:
                    continue
                px = None
                for t_, p_ in cb["history"]:
                    if t_ <= ts:
                        px = p_
                    else:
                        break
                if px is None or px < 0.04:
                    continue
                mp = bprob(cb.get("temp_low", cb["temp"]), cb["temp"], mu, sd)
                ceiling = HIT.get(lead, 0.40)
                ok = px <= ceiling
                if variant in ("V1", "V4"):
                    ok = ok and mp >= px
                if variant in ("V3", "V4"):
                    ok = ok and (mp - px) >= 0.05
                if ok:
                    value = mp - px
                    if best is None or value > best["value"]:
                        best = {"bracket": cb, "px": px, "mp": mp, "value": value}
            if best:
                won = best["bracket"].get("temp_low", best["bracket"]["temp"]) <= resolved <= best["bracket"]["temp"]
                pnl = STAKE * (1 - best["px"]) / best["px"] if won else -STAKE
                bought = {"date": d, "lead": lead,
                          "bracket": f"{best['bracket'].get('temp_low', best['bracket']['temp'])}-{best['bracket']['temp']}",
                          "price": round(best["px"], 3),
                          "model_p": round(best["mp"], 3),
                          "won": won, "pnl": round(pnl, 2)}
                break
        if bought:
            trades.append(bought)

    pnl = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["won"])
    neg_ev = sum(1 for t in trades if t["model_p"] < t["price"])
    by_month = defaultdict(lambda: [0, 0.0])
    for t in trades:
        by_month[t["date"][:7]][0] += 1
        by_month[t["date"][:7]][1] += t["pnl"]
    return {
        "variant": variant,
        "n": len(trades), "wins": wins,
        "win_rate": round(wins / len(trades), 3) if trades else None,
        "pnl": round(pnl, 2),
        "roi": round(pnl / (STAKE * len(trades)), 3) if trades else None,
        "neg_model_ev_trades": neg_ev,
        "avg_price": round(statistics.mean(t["price"] for t in trades), 3) if trades else None,
        "avg_model_p": round(statistics.mean(t["model_p"] for t in trades), 3) if trades else None,
        "by_month": {m: {"n": v[0], "pnl": round(v[1], 0)} for m, v in sorted(by_month.items())},
        "trades": trades,
    }


def main():
    with open(os.path.join(DATA, "polymarket_london.json")) as f:
        events = json.load(f)
    leads = load_leads()

    out = {"live_period": {}, "full_history": {}}
    for variant in ["V0", "V1", "V2", "V3", "V4"]:
        out["live_period"][variant] = replay(events, leads, variant,
                                             start_date="2026-07-10",
                                             end_date="2026-07-19")
        out["full_history"][variant] = replay(events, leads, variant,
                                              start_date="2026-02-01",
                                              end_date="2026-07-19")

    with open(os.path.join(DATA, "diagnosis.json"), "w") as f:
        json.dump(out, f, indent=1)

    for scope in ["live_period", "full_history"]:
        print(f"\n===== {scope.upper()} =====")
        for v, r in out[scope].items():
            print(f"  {v}: n={r['n']} win={r['win_rate']} pnl=${r['pnl']} "
                  f"roi={r['roi']} negEV={r['neg_model_ev_trades']} "
                  f"avg_px={r['avg_price']} avg_modelP={r['avg_model_p']}")
        if scope == "live_period":
            print("  V0 trade detail:")
            for t in out[scope]["V0"]["trades"]:
                print(f"    {t['date']} lead{t['lead']} {t['bracket']}C "
                      f"px={t['price']} modelP={t['model_p']} "
                      f"{'WIN' if t['won'] else 'LOSS'} {t['pnl']}")


if __name__ == "__main__":
    main()
