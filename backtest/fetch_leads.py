#!/usr/bin/env python3
"""
Fetch multi-lead as-issued forecasts (1-7 days ahead) + long climatology.

previous_dayN gives, for each hour, the forecast issued N days earlier —
so the daily max of previous_day3 for date D is what the models said about
D three days in advance.

Outputs:
  backtest/data/leads_{city}.csv   date, lead, per-model daily max
  backtest/data/climo_{city}.csv   date, actual_max (1995 -> present)
"""

import csv
import os
import sys
import time

import requests

CITIES = {
    "london": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London",
               "start": "2021-01-01"},
    "nyc": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York",
            "start": "2024-03-01"},
    "seoul": {"lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul",
              "start": "2024-03-01"},
}

MODELS = {
    "ecmwf": "ecmwf_ifs025",
    "gfs": "gfs_seamless",
    "icon": "icon_seamless",
    "ukmo": "ukmo_seamless",
    "gem": "gem_seamless",
    "jma": "jma_seamless",
}

LEADS = [1, 2, 3, 4, 5, 7]
END = "2026-07-06"
DATA = os.path.join(os.path.dirname(__file__), "data")


def month_chunks(start, end, months=3):
    from datetime import date
    y, m = int(start[:4]), int(start[5:7])
    ey, em = int(end[:4]), int(end[5:7])
    while (y, m) <= (ey, em):
        ny, nm = y, m + months
        while nm > 12:
            ny, nm = ny + 1, nm - 12
        cs = f"{y:04d}-{m:02d}-01"
        # chunk end = day before next chunk start, capped at END
        from datetime import timedelta
        ce = (date(ny, nm, 1) - timedelta(days=1)).isoformat()
        if ce > end:
            ce = end
        yield cs, ce
        y, m = ny, nm


def fetch_chunk(cfg, start, end):
    hvars = [f"temperature_2m_previous_day{n}" for n in LEADS]
    params = {
        "latitude": cfg["lat"], "longitude": cfg["lon"],
        "hourly": ",".join(hvars),
        "models": ",".join(MODELS.values()),
        "start_date": start, "end_date": end,
        "timezone": cfg["tz"],
    }
    r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast",
                     params=params, timeout=180)
    r.raise_for_status()
    hourly = r.json()["hourly"]
    times = hourly["time"]

    # (date, lead) -> {model: [hourly vals]}
    acc = {}
    for key, series in hourly.items():
        if key == "time":
            continue
        lead = model = None
        for n in LEADS:
            for short, api in MODELS.items():
                suffix = f"temperature_2m_previous_day{n}_{api}"
                if key == suffix:
                    lead, model = n, short
                    break
            if lead:
                break
        if lead is None:
            # single-model responses drop the model suffix
            continue
        for t, v in zip(times, series):
            acc.setdefault((t[:10], lead), {}).setdefault(model, []).append(v)

    rows = {}
    for (date_s, lead), models in acc.items():
        row = {}
        for m, vals in models.items():
            clean = [v for v in vals if v is not None]
            row[m] = round(max(clean), 2) if len(clean) >= 20 else None
        rows[(date_s, lead)] = row
    return rows


def main():
    os.makedirs(DATA, exist_ok=True)
    cities = sys.argv[1:] or ["london"]
    for city in cities:
        cfg = CITIES[city]

        # climatology 1995+
        cl_path = os.path.join(DATA, f"climo_{city}.csv")
        if not os.path.exists(cl_path):
            r = requests.get("https://archive-api.open-meteo.com/v1/archive",
                             params={"latitude": cfg["lat"], "longitude": cfg["lon"],
                                     "daily": "temperature_2m_max",
                                     "start_date": "1995-01-01", "end_date": END,
                                     "timezone": cfg["tz"]}, timeout=120)
            d = r.json()["daily"]
            with open(cl_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["date", "actual_max"])
                for t, v in zip(d["time"], d["temperature_2m_max"]):
                    w.writerow([t, v])
            print(f"[{city}] climatology -> {cl_path}")

        all_rows = {}
        for cs, ce in month_chunks(cfg["start"], END):
            print(f"[{city}] leads {cs}..{ce}", flush=True)
            for attempt in range(4):
                try:
                    all_rows.update(fetch_chunk(cfg, cs, ce))
                    break
                except Exception as e:
                    print(f"  retry {attempt}: {e}", flush=True)
                    time.sleep(8)

        path = os.path.join(DATA, f"leads_{city}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "lead"] + list(MODELS.keys()))
            for (date_s, lead) in sorted(all_rows):
                row = all_rows[(date_s, lead)]
                w.writerow([date_s, lead] + [row.get(m) for m in MODELS])
        print(f"[{city}] wrote {len(all_rows)} rows -> {path}", flush=True)


if __name__ == "__main__":
    main()
