#!/usr/bin/env python3
"""
Model-skill profitability study.

Question: is the raw forecast signal good enough to base betting logic on?

1. Skill by lead time (1-7d): error stats + exact-bracket hit rate
   (= the break-even price for buying the model's favorite bracket).
2. Multi-year betting sim vs a climatology bookmaker (naive counterparty).
3. Anchor vs the real market (5 months): buy the model-modal bracket at
   market prices — at midnight (lead 1) and at market open (lead 2-3).

Outputs backtest/data/skill_results.json + a printed summary.
"""

import csv
import json
import math
import os
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

DATA = os.path.join(os.path.dirname(__file__), "data")
MODELS = ["ecmwf", "gfs", "icon", "ukmo", "gem", "jma"]
STAKE = 10.0

CITY_TZ = {"london": "Europe/London", "nyc": "America/New_York",
           "seoul": "Asia/Seoul"}


def br(x):
    """Integer bracket a temperature falls in (Polymarket-style rounding)."""
    return math.floor(x + 0.5)


def norm_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def bracket_prob(t, mu, sigma):
    return norm_cdf(t + 0.5, mu, sigma) - norm_cdf(t - 0.5, mu, sigma)


def load_leads(city):
    """-> {(date, lead): {'median':, 'n':, 'std':}}"""
    out = {}
    with open(os.path.join(DATA, f"leads_{city}.csv")) as f:
        for r in csv.DictReader(f):
            vals = [float(r[m]) for m in MODELS if r[m] not in ("", None)]
            if len(vals) < 2:
                continue
            out[(r["date"], int(r["lead"]))] = {
                "median": statistics.median(vals),
                "n": len(vals),
                "std": statistics.pstdev(vals),
            }
    return out


def load_actuals(city):
    out = {}
    with open(os.path.join(DATA, f"climo_{city}.csv")) as f:
        for r in csv.DictReader(f):
            if r["actual_max"] not in ("", None):
                out[r["date"]] = float(r["actual_max"])
    return out


# ─── 1. SKILL BY LEAD ─────────────────────────────────────────────────────────

def skill_by_lead(leads, actuals, era):
    """era: '2models' (n<=2) or '5plus' (n>=5)"""
    res = defaultdict(list)
    for (d, lead), f in leads.items():
        a = actuals.get(d)
        if a is None:
            continue
        if era == "2models" and f["n"] > 2:
            continue
        if era == "5plus" and f["n"] < 5:
            continue
        res[lead].append((f["median"], a, f["std"]))

    out = {}
    for lead, rows in sorted(res.items()):
        errs = [a - m for m, a, _ in rows]
        hits = sum(1 for m, a, _ in rows if br(m) == br(a))
        near = sum(1 for m, a, _ in rows if abs(br(m) - br(a)) <= 1)
        out[lead] = {
            "n_days": len(rows),
            "bias": round(statistics.mean(errs), 2),
            "mae": round(statistics.mean(map(abs, errs)), 2),
            "residual_std": round(statistics.pstdev(errs), 2),
            "mean_spread": round(statistics.mean(s for _, _, s in rows), 2),
            "exact_bracket_hit": round(hits / len(rows), 3),
            "within_1_bracket": round(near / len(rows), 3),
        }
    return out


# ─── 2. CLIMATOLOGY BOOKMAKER SIM ─────────────────────────────────────────────

def climo_dist(actuals_by_doy, d, first_year):
    """Bracket probabilities from prior years, DOY +/-5 window."""
    target = date.fromisoformat(d)
    counts = defaultdict(int)
    total = 0
    for delta in range(-5, 6):
        doy_date = target + timedelta(days=delta)
        key = (doy_date.month, doy_date.day)
        for y, v in actuals_by_doy.get(key, []):
            if first_year <= y < target.year:
                counts[br(v)] += 1
                total += 1
    if total < 50:
        return None
    lo, hi = min(counts), max(counts)
    probs = {}
    alpha = 1.0
    denom = total + alpha * (hi - lo + 1)
    for t in range(lo, hi + 1):
        probs[t] = (counts.get(t, 0) + alpha) / denom
    return probs


def climo_sim(leads, actuals, city, lead, sigma_emp, min_edge=0.15, vig=0.0):
    """Bet vs climatology-priced bookmaker across all available history."""
    actuals_by_doy = defaultdict(list)
    for d, v in actuals.items():
        dd = date.fromisoformat(d)
        actuals_by_doy[(dd.month, dd.day)].append((dd.year, v))

    trades = []
    for (d, l), f in leads.items():
        if l != lead:
            continue
        a = actuals.get(d)
        if a is None:
            continue
        dist = climo_dist(actuals_by_doy, d, 1995)
        if not dist:
            continue
        for t, climo_p in dist.items():
            price = min(0.99, climo_p * (1 + vig))
            our_p = bracket_prob(t, f["median"], sigma_emp)
            if our_p - price >= min_edge and 0.02 <= price <= 0.9:
                won = br(a) == t
                pnl = STAKE * (1 - price) / price if won else -STAKE
                trades.append((d, t, round(price, 3), round(our_p, 3), won,
                               round(pnl, 2)))

    pnl = sum(t[5] for t in trades)
    wins = sum(1 for t in trades if t[4])
    by_year = defaultdict(float)
    for t in trades:
        by_year[t[0][:4]] += t[5]
    return {
        "city": city, "lead": lead, "min_edge": min_edge, "vig": vig,
        "n_trades": len(trades),
        "win_rate": round(wins / len(trades), 3) if trades else None,
        "total_pnl": round(pnl, 2),
        "roi": round(pnl / (STAKE * len(trades)), 3) if trades else None,
        "pnl_by_year": {y: round(v, 0) for y, v in sorted(by_year.items())},
    }


# ─── 3. REAL-MARKET ANCHOR ────────────────────────────────────────────────────

def market_anchor(city, leads, when="midnight"):
    """Buy the model-modal bracket at real market prices.
    when='midnight' -> price at 00:00 local target day, lead-1 forecast.
    when='open'     -> first market price, forecast at matching lead."""
    path = os.path.join(DATA, f"polymarket_{city}.json")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        events = json.load(f)
    tz = ZoneInfo(CITY_TZ[city])

    trades = []
    prices_paid = []
    for ev in events:
        winners = [b for b in ev["brackets"]
                   if b["final"] is not None and b["final"] > 0.9]
        if len(winners) != 1:
            continue
        resolved = winners[0]["temp"]
        d = date.fromisoformat(ev["date"])
        unit = ev.get("unit", "C")

        if when == "midnight":
            ts = int(datetime(d.year, d.month, d.day, tzinfo=tz).timestamp())
            lead = 1
        else:
            starts = [b["history"][0][0] for b in ev["brackets"] if b["history"]]
            if not starts:
                continue
            ts = min(starts) + 3600  # one hour after open
            days_out = (datetime(d.year, d.month, d.day, 23, tzinfo=tz).timestamp()
                        - ts) / 86400
            lead = max(1, min(7, round(days_out)))
            if lead == 6:
                lead = 7

        f = leads.get((ev["date"], lead))
        if not f:
            continue
        mu = f["median"] * 9 / 5 + 32 if unit == "F" else f["median"]

        modal = br(mu)
        cands = [b for b in ev["brackets"] if not b["is_upper"] and not b["is_lower"]
                 and b["temp"] == modal]
        if not cands:
            continue
        b = cands[0]
        px = None
        for t_, p_ in b["history"]:
            if t_ <= ts:
                px = p_
            else:
                break
        if px is None or px < 0.02 or px > 0.9:
            continue
        won = resolved == modal
        pnl = STAKE * (1 - px) / px if won else -STAKE
        prices_paid.append(px)
        trades.append({"date": ev["date"], "bracket": modal, "price": round(px, 3),
                       "won": won, "pnl": round(pnl, 2)})

    if not trades:
        return {"city": city, "when": when, "n_trades": 0}
    pnl = sum(t["pnl"] for t in trades)
    wins = sum(1 for t in trades if t["won"])
    by_month = defaultdict(float)
    for t in trades:
        by_month[t["date"][:7]] += t["pnl"]
    return {
        "city": city, "when": when,
        "n_trades": len(trades),
        "hit_rate": round(wins / len(trades), 3),
        "avg_price_paid": round(statistics.mean(prices_paid), 3),
        "total_pnl": round(pnl, 2),
        "roi": round(pnl / (STAKE * len(trades)), 3),
        "pnl_by_month": {m: round(v, 0) for m, v in sorted(by_month.items())},
    }


def main():
    results = {}
    for city in ["london", "nyc", "seoul"]:
        lp = os.path.join(DATA, f"leads_{city}.csv")
        if not os.path.exists(lp):
            continue
        leads = load_leads(city)
        actuals = load_actuals(city)

        entry = {"skill_5plus": skill_by_lead(leads, actuals, "5plus")}
        if city == "london":
            entry["skill_2models"] = skill_by_lead(leads, actuals, "2models")
            # sigma_emp from lead-specific residual std (5+ era)
            sims = []
            for lead in [1, 2, 3, 5, 7]:
                s = entry["skill_5plus"].get(lead, {}).get("residual_std")
                s2 = entry["skill_2models"].get(lead, {}).get("residual_std")
                sigma = s or s2
                if not sigma:
                    continue
                for vig in (0.0, 0.05):
                    sims.append(climo_sim(leads, actuals, city, lead, sigma,
                                          min_edge=0.15, vig=vig))
            entry["climo_sims"] = sims

        entry["market_anchor_midnight"] = market_anchor(city, leads, "midnight")
        entry["market_anchor_open"] = market_anchor(city, leads, "open")
        results[city] = entry

    out = os.path.join(DATA, "skill_results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)

    for city, e in results.items():
        print(f"\n===== {city.upper()} =====")
        print("  skill by lead (5+ models):")
        for lead, s in e["skill_5plus"].items():
            print(f"    lead {lead}d: n={s['n_days']} mae={s['mae']} "
                  f"hit={s['exact_bracket_hit']} within1={s['within_1_bracket']}")
        if "skill_2models" in e:
            print("  skill by lead (2-model era 2021-24):")
            for lead, s in e["skill_2models"].items():
                print(f"    lead {lead}d: n={s['n_days']} mae={s['mae']} "
                      f"hit={s['exact_bracket_hit']}")
        for sim in e.get("climo_sims", []):
            print(f"  climo-sim lead={sim['lead']} vig={sim['vig']}: "
                  f"trades={sim['n_trades']} win={sim['win_rate']} "
                  f"pnl=${sim['total_pnl']} roi={sim['roi']}")
        for key in ("market_anchor_midnight", "market_anchor_open"):
            a = e.get(key)
            if a and a.get("n_trades"):
                print(f"  {key}: n={a['n_trades']} hit={a['hit_rate']} "
                      f"avg_price={a['avg_price_paid']} pnl=${a['total_pnl']} "
                      f"roi={a['roi']}")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
