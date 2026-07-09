#!/usr/bin/env python3
"""
Fetch historical day-ahead forecasts (as issued) per model + observed actuals.

Uses Open-Meteo's previous-runs API: temperature_2m_previous_day1 is the
forecast for each hour as issued by the model run ~24h earlier — i.e. exactly
what our bot sees when it trades the day before.

Output: backtest/data/weather_{city}.csv with one row per date:
  date, actual_max, ecmwf, gfs, icon, ukmo, gem, jma  (day-ahead max forecasts)
"""

import csv
import os
import sys
import time

import requests

CITIES = {
    "london": {"lat": 51.5074, "lon": -0.1278, "tz": "Europe/London"},
    "nyc": {"lat": 40.7128, "lon": -74.0060, "tz": "America/New_York"},
    "seoul": {"lat": 37.5665, "lon": 126.9780, "tz": "Asia/Seoul"},
}

MODELS = {
    "ecmwf": "ecmwf_ifs025",
    "gfs": "gfs_seamless",
    "icon": "icon_seamless",
    "ukmo": "ukmo_seamless",
    "gem": "gem_seamless",
    "jma": "jma_seamless",
}

START = "2021-01-01"
END = "2026-07-06"

OUT_DIR = os.path.join(os.path.dirname(__file__), "data")


def fetch_chunk(city_cfg, start, end):
    """Fetch hourly previous_day1 forecasts for all models + return daily maxes."""
    params = {
        "latitude": city_cfg["lat"],
        "longitude": city_cfg["lon"],
        "hourly": "temperature_2m_previous_day1",
        "models": ",".join(MODELS.values()),
        "start_date": start,
        "end_date": end,
        "timezone": city_cfg["tz"],
    }
    r = requests.get("https://previous-runs-api.open-meteo.com/v1/forecast",
                     params=params, timeout=120)
    r.raise_for_status()
    d = r.json()
    hourly = d["hourly"]
    times = hourly["time"]

    daily = {}  # date -> {model: [vals]}
    for key, series in hourly.items():
        if key == "time":
            continue
        model = None
        for short, api_name in MODELS.items():
            if key.endswith(api_name):
                model = short
                break
        if model is None:
            continue
        for t, v in zip(times, series):
            date = t[:10]
            daily.setdefault(date, {}).setdefault(model, []).append(v)

    out = {}
    for date, models in daily.items():
        row = {}
        for m, vals in models.items():
            clean = [v for v in vals if v is not None]
            row[m] = round(max(clean), 2) if len(clean) >= 20 else None
        out[date] = row
    return out


def fetch_actuals(city_cfg, start, end):
    params = {
        "latitude": city_cfg["lat"],
        "longitude": city_cfg["lon"],
        "daily": "temperature_2m_max",
        "start_date": start,
        "end_date": end,
        "timezone": city_cfg["tz"],
    }
    r = requests.get("https://archive-api.open-meteo.com/v1/archive",
                     params=params, timeout=120)
    r.raise_for_status()
    d = r.json()["daily"]
    return dict(zip(d["time"], d["temperature_2m_max"]))


def year_chunks(start, end):
    sy, ey = int(start[:4]), int(end[:4])
    for y in range(sy, ey + 1):
        cs = f"{y}-01-01" if y > sy else start
        ce = f"{y}-12-31" if y < ey else end
        yield cs, ce


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    cities = sys.argv[1:] or ["london"]
    for city in cities:
        cfg = CITIES[city]
        forecasts = {}
        for cs, ce in year_chunks(START, END):
            print(f"[{city}] forecasts {cs}..{ce}")
            for attempt in range(3):
                try:
                    forecasts.update(fetch_chunk(cfg, cs, ce))
                    break
                except Exception as e:
                    print(f"  retry {attempt}: {e}")
                    time.sleep(5)
        print(f"[{city}] actuals")
        actuals = fetch_actuals(cfg, START, END)

        path = os.path.join(OUT_DIR, f"weather_{city}.csv")
        with open(path, "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["date", "actual_max"] + list(MODELS.keys()))
            for date in sorted(forecasts):
                row = forecasts[date]
                w.writerow([date, actuals.get(date)] +
                           [row.get(m) for m in MODELS.keys()])
        n = len(forecasts)
        print(f"[{city}] wrote {n} days -> {path}")


if __name__ == "__main__":
    main()
