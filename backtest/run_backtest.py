#!/usr/bin/env python3
"""
Backtest the Polymarket weather strategy.

A. Calibration study (multi-year weather data):
   Is P(high > t) = 1 - N(median, sigma_spread).cdf(t+0.5) calibrated?

B. Strategy replay (resolved Polymarket events):
   Replay the live bot's exact rules against real market prices at a
   realistic decision time; compare model skill vs market skill head-on.

Outputs backtest/data/results.json and prints a summary.
"""

import csv
import json
import math
import os
import statistics
from datetime import datetime, date, timezone, timedelta
from zoneinfo import ZoneInfo

DATA = os.path.join(os.path.dirname(__file__), "data")
MODELS = ["ecmwf", "gfs", "icon", "ukmo", "gem", "jma"]
STAKE = 10.0


def norm_cdf(x, mu, sigma):
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def p_over(threshold_plus_half, mu, sigma):
    return 1.0 - norm_cdf(threshold_plus_half, mu, sigma)


def load_weather(city):
    rows = []
    with open(os.path.join(DATA, f"weather_{city}.csv")) as f:
        for r in csv.DictReader(f):
            fc = {m: float(r[m]) for m in MODELS if r[m] not in ("", None)}
            if r["actual_max"] in ("", None) or len(fc) < 2:
                continue
            vals = list(fc.values())
            rows.append({
                "date": r["date"],
                "actual": float(r["actual_max"]),
                "n_models": len(vals),
                "median": statistics.median(vals),
                "std": statistics.pstdev(vals),
            })
    return rows


# ─── A. CALIBRATION ───────────────────────────────────────────────────────────

def calibration(rows, sigma_mult=1.0, sigma_floor=0.0, label=""):
    """Reliability + Brier over integer thresholds near the median."""
    preds = []
    for r in rows:
        sigma = max(r["std"] * sigma_mult, sigma_floor)
        base = round(r["median"])
        for t in range(base - 3, base + 4):
            p = p_over(t + 0.5, r["median"], sigma)
            outcome = 1.0 if r["actual"] > t + 0.5 else 0.0
            preds.append((p, outcome))

    brier = sum((p - o) ** 2 for p, o in preds) / len(preds)

    bins = [[] for _ in range(10)]
    for p, o in preds:
        bins[min(int(p * 10), 9)].append(o)
    reliability = []
    for i, b in enumerate(bins):
        if b:
            reliability.append({
                "bin": f"{i*10}-{i*10+10}%",
                "predicted_mid": i * 0.1 + 0.05,
                "observed": sum(b) / len(b),
                "n": len(b),
            })
    return {"label": label, "n_predictions": len(preds), "brier": round(brier, 4),
            "reliability": reliability}


def residual_stats(rows):
    errs = [r["actual"] - r["median"] for r in rows]
    abs_errs = [abs(e) for e in errs]
    spreads = [r["std"] for r in rows]
    # correlation spread vs abs error
    n = len(errs)
    ms, ma = statistics.mean(spreads), statistics.mean(abs_errs)
    cov = sum((s - ms) * (a - ma) for s, a in zip(spreads, abs_errs)) / n
    ss, sa = statistics.pstdev(spreads), statistics.pstdev(abs_errs)
    corr = cov / (ss * sa) if ss > 0 and sa > 0 else 0

    by_year = {}
    for r, e in zip(rows, errs):
        by_year.setdefault(r["date"][:4], []).append(e)

    return {
        "n_days": n,
        "bias": round(statistics.mean(errs), 3),
        "mae": round(ma, 3),
        "rmse": round(math.sqrt(statistics.mean(e * e for e in errs)), 3),
        "residual_std": round(statistics.pstdev(errs), 3),
        "mean_ensemble_spread": round(ms, 3),
        "overconfidence_ratio": round(statistics.pstdev(errs) / ms, 2) if ms else None,
        "spread_abs_error_corr": round(corr, 3),
        "by_year": {y: {"n": len(v), "bias": round(statistics.mean(v), 2),
                        "mae": round(statistics.mean(map(abs, v)), 2)}
                    for y, v in sorted(by_year.items())},
    }


# ─── B. STRATEGY REPLAY ───────────────────────────────────────────────────────

def price_at(history, ts):
    """Last traded price at or before unix ts."""
    best = None
    for t, p in history:
        if t <= ts:
            best = p
        else:
            break
    return best


def market_prob_over(brackets, t, price_key):
    prob = 0.0
    seen = False
    for b in brackets:
        p = b.get(price_key)
        if p is None:
            return None
        seen = True
        if b["is_upper"] or b["temp"] > t:
            prob += p
    return prob if seen else None


def resolve(brackets):
    """Return resolved bracket temp, or None."""
    winners = [b for b in brackets if b["final"] is not None and b["final"] > 0.9]
    if len(winners) != 1:
        return None
    return winners[0]


def replay(events, weather_by_date, tz_name, sigma_mult=1.0, sigma_floor=0.0,
           min_edge=0.15, decision_hour=0, label=""):
    """Replay the live strategy. decision_hour: local hour on target day
    (0 = midnight = pure day-ahead)."""
    tz = ZoneInfo(tz_name)
    trades = []
    skipped = {"no_res": 0, "no_price": 0, "no_weather": 0, "no_bracket": 0}
    model_sq, market_sq, n_scored = 0.0, 0.0, 0

    for ev in events:
        w = weather_by_date.get(ev["date"])
        if not w:
            skipped["no_weather"] += 1
            continue
        res = resolve(ev["brackets"])
        if res is None:
            skipped["no_res"] += 1
            continue

        d = date.fromisoformat(ev["date"])
        ts = int(datetime(d.year, d.month, d.day, decision_hour, 0,
                          tzinfo=tz).timestamp())
        for b in ev["brackets"]:
            b["px"] = price_at(b["history"], ts)
        priced = [b for b in ev["brackets"] if b["px"] is not None]
        if len(priced) < 6:
            skipped["no_price"] += 1
            continue

        unit = ev.get("unit", "C")
        mu = w["median"] * 9 / 5 + 32 if unit == "F" else w["median"]
        sd_raw = w["std"] * 9 / 5 if unit == "F" else w["std"]
        sd = max(sd_raw * sigma_mult, sigma_floor)

        # actual outcome value in native unit
        actual_temp = res["temp"]

        # threshold pick: max |edge| within market prob band (live logic)
        best = None
        for b in ev["brackets"]:
            if b["is_upper"] or b["px"] is None:
                continue
            t = b["temp"]
            mp = market_prob_over(ev["brackets"], t, "px")
            if mp is None or not (0.03 <= mp <= 0.97):
                continue
            op = p_over(t + 0.5, mu, sd)
            edge = op - mp
            if best is None or abs(edge) > abs(best["edge"]):
                best = {"t": t, "our": op, "mkt": mp, "edge": edge}

        if best is None:
            skipped["no_bracket"] += 1
            continue

        # head-to-head skill on the chosen threshold
        outcome = 1.0 if actual_temp > best["t"] else 0.0
        model_sq += (best["our"] - outcome) ** 2
        market_sq += (best["mkt"] - outcome) ** 2
        n_scored += 1

        sigs = []
        if abs(best["edge"]) >= min_edge and sd_raw * sigma_mult <= 3.0 * (9/5 if unit == "F" else 1):
            sigs.append("consensus_edge")
        hc_std_cap = 1.0 * (9/5 if unit == "F" else 1)
        if sd <= hc_std_cap:
            if best["our"] >= 0.75 and best["our"] - best["mkt"] > 0:
                sigs.append("high_confidence")
            elif (1 - best["our"]) >= 0.75 and (1 - best["our"]) - (1 - best["mkt"]) > 0:
                sigs.append("high_confidence")

        for strat in sigs:
            side = "YES" if best["edge"] > 0 else "NO"
            entry = best["mkt"] if side == "YES" else 1 - best["mkt"]
            won = (outcome == 1.0) if side == "YES" else (outcome == 0.0)
            if entry <= 0.005:
                continue
            pnl = STAKE * (1 - entry) / entry if won else -STAKE
            trades.append({
                "date": ev["date"], "strategy": strat, "side": side,
                "threshold": best["t"], "entry": round(entry, 3),
                "our_p": round(best["our"], 3), "mkt_p": round(best["mkt"], 3),
                "edge": round(best["edge"], 3), "won": won,
                "pnl": round(pnl, 2),
            })

    total_pnl = sum(t["pnl"] for t in trades)
    staked = STAKE * len(trades)
    wins = sum(1 for t in trades if t["won"])
    return {
        "label": label,
        "params": {"sigma_mult": sigma_mult, "sigma_floor": sigma_floor,
                   "min_edge": min_edge, "decision_hour": decision_hour},
        "events_scored": n_scored,
        "model_brier": round(model_sq / n_scored, 4) if n_scored else None,
        "market_brier": round(market_sq / n_scored, 4) if n_scored else None,
        "n_trades": len(trades),
        "wins": wins,
        "win_rate": round(wins / len(trades), 3) if trades else None,
        "total_pnl": round(total_pnl, 2),
        "roi": round(total_pnl / staked, 3) if staked else None,
        "skipped": skipped,
        "trades": trades,
    }


CITY_TZ = {
    "london": "Europe/London",
    "nyc": "America/New_York",
    "seoul": "Asia/Seoul",
}

CONFIGS = [
    dict(sigma_mult=1.0, sigma_floor=0.0, min_edge=0.15, decision_hour=0,
         label="LIVE CONFIG (as deployed)"),
    dict(sigma_mult=1.5, sigma_floor=0.0, min_edge=0.15, decision_hour=0,
         label="sigma x1.5"),
    dict(sigma_mult=2.0, sigma_floor=0.0, min_edge=0.15, decision_hour=0,
         label="sigma x2.0"),
    dict(sigma_mult=1.0, sigma_floor=1.2, min_edge=0.15, decision_hour=0,
         label="sigma floor 1.2"),
    dict(sigma_mult=2.0, sigma_floor=1.8, min_edge=0.15, decision_hour=0,
         label="sigma x2 + floor 1.8"),
    dict(sigma_mult=1.0, sigma_floor=0.0, min_edge=0.25, decision_hour=0,
         label="min_edge 0.25"),
    dict(sigma_mult=1.0, sigma_floor=0.0, min_edge=0.35, decision_hour=0,
         label="min_edge 0.35"),
    dict(sigma_mult=2.0, sigma_floor=1.8, min_edge=0.25, decision_hour=0,
         label="sigma x2+floor1.8, edge 0.25"),
    dict(sigma_mult=1.0, sigma_floor=0.0, min_edge=0.15, decision_hour=9,
         label="decide 09:00 same day"),
    dict(sigma_mult=1.0, sigma_floor=0.0, min_edge=0.15, decision_hour=14,
         label="decide 14:00 same day"),
]


def combine(replays_by_city, cfg_label):
    """Aggregate one config's replays across cities into a portfolio view."""
    trades, n_scored = [], 0
    model_sq = market_sq = 0.0
    for city, reps in replays_by_city.items():
        r = next(x for x in reps if x["label"] == cfg_label)
        for t in r["trades"]:
            trades.append({**t, "city": city})
        if r["events_scored"]:
            n_scored += r["events_scored"]
            model_sq += r["model_brier"] * r["events_scored"]
            market_sq += r["market_brier"] * r["events_scored"]
    total_pnl = sum(t["pnl"] for t in trades)
    staked = STAKE * len(trades)
    wins = sum(1 for t in trades if t["won"])
    return {
        "label": cfg_label,
        "events_scored": n_scored,
        "model_brier": round(model_sq / n_scored, 4) if n_scored else None,
        "market_brier": round(market_sq / n_scored, 4) if n_scored else None,
        "n_trades": len(trades),
        "wins": wins,
        "win_rate": round(wins / len(trades), 3) if trades else None,
        "total_pnl": round(total_pnl, 2),
        "roi": round(total_pnl / staked, 3) if staked else None,
        "trades": trades,
    }


def main():
    results = {}

    # A: calibration on London (deepest history)
    weather_london = load_weather("london")
    era5plus = [r for r in weather_london if r["n_models"] >= 5]
    results["residuals_full"] = residual_stats(weather_london)
    results["residuals_5models"] = residual_stats(era5plus)
    results["calibration"] = [
        calibration(era5plus, 1.0, 0.0, "live config (raw ensemble spread)"),
        calibration(era5plus, 1.5, 0.0, "sigma x1.5"),
        calibration(era5plus, 2.0, 0.0, "sigma x2.0"),
        calibration(era5plus, 1.0, 1.2, "sigma floor 1.2C"),
        calibration(era5plus, 1.5, 1.5, "sigma x1.5 + floor 1.5C"),
        calibration(era5plus, 2.0, 1.8, "sigma x2.0 + floor 1.8C"),
    ]

    # B: per-city replays + combined portfolio
    replays_by_city = {}
    for city, tz in CITY_TZ.items():
        wpath = os.path.join(DATA, f"weather_{city}.csv")
        ppath = os.path.join(DATA, f"polymarket_{city}.json")
        if not (os.path.exists(wpath) and os.path.exists(ppath)):
            continue
        weather_by_date = {r["date"]: r for r in load_weather(city)}
        with open(ppath) as f:
            events = json.load(f)
        reps = [replay(events, weather_by_date, tz, c["sigma_mult"],
                       c["sigma_floor"], c["min_edge"], c["decision_hour"],
                       c["label"]) for c in CONFIGS]
        replays_by_city[city] = reps
        results[f"n_events_{city}"] = len(events)

    results["replays_by_city"] = replays_by_city
    results["combined"] = [combine(replays_by_city, c["label"]) for c in CONFIGS]

    out = os.path.join(DATA, "results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=1)

    print("=== RESIDUALS London (5+ model era) ===")
    for k, v in results["residuals_5models"].items():
        if k != "by_year":
            print(f"  {k}: {v}")
    print("\n=== CALIBRATION London (Brier, lower=better) ===")
    for c in results["calibration"]:
        print(f"  {c['label']}: {c['brier']}  (n={c['n_predictions']})")
    print("\n=== COMBINED STRATEGY REPLAYS (all cities) ===")
    for r in results["combined"]:
        print(f"  {r['label']}: trades={r['n_trades']} win={r['win_rate']} "
              f"pnl=${r['total_pnl']} roi={r['roi']} | "
              f"model_brier={r['model_brier']} vs market_brier={r['market_brier']} "
              f"(events={r['events_scored']})")
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
