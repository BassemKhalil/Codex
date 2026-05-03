"""
Weather forecast fetching via Open-Meteo API.
Pulls from multiple NWP models and computes consensus statistics.
"""

import math

try:
    import requests as _req

    def _fetch_json(url):
        resp = _req.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
except ImportError:
    import urllib.request
    import json as _json

    def _fetch_json(url):
        with urllib.request.urlopen(url, timeout=10) as resp:
            return _json.loads(resp.read().decode())


MODELS = [
    ("ECMWF IFS", "ecmwf"),
    ("GFS",       "gfs"),
    ("UKMO",      "ukmo"),
    ("GEM",       "gem"),
    ("ICON",      "dwd-icon"),
    ("JMA",       "jma"),
]


def c_to_f(c):
    return c * 9.0 / 5.0 + 32.0


def fetch_forecast(endpoint, lat, lon, timezone, target_date):
    url = (
        f"https://api.open-meteo.com/v1/{endpoint}"
        f"?latitude={lat}&longitude={lon}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&timezone={timezone}"
    )
    data = _fetch_json(url)
    daily = data["daily"]
    dates = daily["time"]
    if target_date in dates:
        idx = dates.index(target_date)
        return daily["temperature_2m_max"][idx], daily["temperature_2m_min"][idx]
    return None, None


def fetch_all_models(lat, lon, timezone, target_date):
    """Fetch forecasts from all models. Returns (results, errors)."""
    results = []
    errors = []
    for name, endpoint in MODELS:
        try:
            high_c, low_c = fetch_forecast(endpoint, lat, lon, timezone, target_date)
            if high_c is None:
                errors.append(name)
                continue
            results.append({"model": name, "high_c": high_c, "low_c": low_c})
        except Exception:
            errors.append(name)
    return results, errors


def compute_consensus(results):
    """Compute consensus statistics from model results."""
    if not results:
        return None
    highs = [r["high_c"] for r in results]
    lows = [r["low_c"] for r in results]
    n = len(highs)
    mean_h = sum(highs) / n
    sorted_h = sorted(highs)
    if n % 2 == 1:
        median_h = sorted_h[n // 2]
    else:
        median_h = (sorted_h[n // 2 - 1] + sorted_h[n // 2]) / 2.0
    std_h = math.sqrt(sum((x - mean_h) ** 2 for x in highs) / n)

    mean_l = sum(lows) / n
    sorted_l = sorted(lows)
    if n % 2 == 1:
        median_l = sorted_l[n // 2]
    else:
        median_l = (sorted_l[n // 2 - 1] + sorted_l[n // 2]) / 2.0

    return {
        "mean_high": mean_h,
        "median_high": median_h,
        "min_high": min(highs),
        "max_high": max(highs),
        "std_high": std_h,
        "mean_low": mean_l,
        "median_low": median_l,
        "model_count": n,
    }


def fetch_actual_temperature(lat, lon, timezone, target_date):
    """Fetch observed high temperature from the Open-Meteo archive API."""
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={target_date}&end_date={target_date}"
        f"&daily=temperature_2m_max"
        f"&timezone={timezone}"
    )
    try:
        data = _fetch_json(url)
        daily = data["daily"]
        if target_date in daily["time"]:
            idx = daily["time"].index(target_date)
            return daily["temperature_2m_max"][idx]
    except Exception:
        pass
    return None
