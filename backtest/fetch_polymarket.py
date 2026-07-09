#!/usr/bin/env python3
"""
Harvest resolved Polymarket daily-temperature events + historical prices.

For each date in range, probe the predictable event slug
(highest-temperature-in-{city}-on-{month}-{day}-{year}), pull its bracket
markets, resolution (final 0/1 prices), and per-token CLOB price history.

Output: backtest/data/polymarket_{city}.json — list of events:
  {date, event_id, unit, brackets: [{temp, is_lower, is_upper, final,
   history: [[ts, price], ...]}]}
"""

import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, timedelta

import requests

MONTHS = ["january", "february", "march", "april", "may", "june", "july",
          "august", "september", "october", "november", "december"]

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")


def get(url, params=None, retries=3):
    for i in range(retries):
        try:
            r = requests.get(url, params=params, timeout=30)
            if r.status_code == 429:
                time.sleep(3)
                continue
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == retries - 1:
                return None
            time.sleep(2)
    return None


def slug_for(city, d):
    return f"highest-temperature-in-{city}-on-{MONTHS[d.month-1]}-{d.day}-{d.year}"


def extract_temp(question):
    m = re.search(r"(-?\d+)\s*°?\s*([CF])", question)
    if m:
        return int(m.group(1)), m.group(2)
    return None, None


def _fetch_history(token, target_date):
    # interval=max silently returns [] for markets older than ~3 weeks;
    # explicit startTs/endTs works for the full archive.
    from datetime import datetime, timezone
    start = int(datetime(target_date.year, target_date.month, target_date.day,
                         tzinfo=timezone.utc).timestamp()) - 5 * 86400
    end = start + 7 * 86400
    h = get("https://clob.polymarket.com/prices-history",
            params={"market": token, "startTs": start, "endTs": end,
                    "fidelity": 60})
    if h and "history" in h:
        return [[p["t"], p["p"]] for p in h["history"]]
    return []


def harvest_event(city, d, pool):
    events = get("https://gamma-api.polymarket.com/events",
                 params={"slug": slug_for(city, d)})
    if not events:
        return None
    ev = events[0]
    brackets = []
    unit = "C"
    futures = {}
    for mkt in ev.get("markets", []):
        q = mkt.get("question", "")
        temp, u = extract_temp(q)
        if temp is None:
            continue
        if u:
            unit = u
        ql = q.lower()
        is_lower = "or below" in ql or "or less" in ql
        is_upper = "or higher" in ql or "or above" in ql

        prices = mkt.get("outcomePrices")
        final = None
        if prices:
            if isinstance(prices, str):
                prices = json.loads(prices)
            final = float(prices[0])

        b = {"temp": temp, "is_lower": is_lower, "is_upper": is_upper,
             "final": final, "history": []}
        tokens = mkt.get("clobTokenIds")
        if tokens:
            if isinstance(tokens, str):
                tokens = json.loads(tokens)
            if tokens:
                futures[pool.submit(_fetch_history, tokens[0], d)] = b
        brackets.append(b)

    for fut, b in futures.items():
        b["history"] = fut.result()

    if not brackets:
        return None
    brackets.sort(key=lambda b: b["temp"])
    return {
        "date": d.isoformat(),
        "event_id": ev.get("id"),
        "closed": ev.get("closed"),
        "unit": unit,
        "brackets": brackets,
    }


def main():
    city = sys.argv[1] if len(sys.argv) > 1 else "london"
    start = date.fromisoformat(sys.argv[2]) if len(sys.argv) > 2 else date(2026, 2, 1)
    end = date.fromisoformat(sys.argv[3]) if len(sys.argv) > 3 else date(2026, 7, 6)

    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, f"polymarket_{city}.json")
    out = []
    if os.path.exists(path):
        with open(path) as f:
            out = json.load(f)
    done = {e["date"] for e in out}

    pool = ThreadPoolExecutor(max_workers=6)
    d = start
    while d <= end:
        if d.isoformat() in done:
            d += timedelta(days=1)
            continue
        ev = harvest_event(city, d, pool)
        if ev:
            out.append(ev)
            print(f"{d} OK ({len(ev['brackets'])} brackets)", flush=True)
        else:
            print(f"{d} -", flush=True)
        if len(out) % 10 == 0:
            with open(path, "w") as f:
                json.dump(out, f)
        d += timedelta(days=1)

    out.sort(key=lambda e: e["date"])
    with open(path, "w") as f:
        json.dump(out, f)
    print(f"wrote {len(out)} events -> {path}", flush=True)


if __name__ == "__main__":
    main()
