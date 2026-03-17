#!/usr/bin/env python3
"""
Polymarket Weather Forecast Comparison Tool

Fetches forecasts from multiple weather models via Open-Meteo API
and provides consensus analysis for informed betting on temperature contracts.
"""

import math
from datetime import date, timedelta

try:
    import requests
    def fetch_json(url):
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
except ImportError:
    import urllib.request
    import json
    def fetch_json(url):
        with urllib.request.urlopen(url, timeout=10) as resp:
            return json.loads(resp.read().decode())

# ─── CONFIGURATION ───────────────────────────────────────────────────────────
CITY = "London"
LATITUDE = 51.5074
LONGITUDE = -0.1278
TARGET_DATE = (date.today() + timedelta(days=1)).isoformat()  # tomorrow
TIMEZONE = "Europe/London"
# ─────────────────────────────────────────────────────────────────────────────

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


def fetch_forecast(endpoint):
    url = (
        f"https://api.open-meteo.com/v1/{endpoint}"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f"&timezone={TIMEZONE}"
    )
    data = fetch_json(url)
    daily = data["daily"]
    dates = daily["time"]
    if TARGET_DATE in dates:
        idx = dates.index(TARGET_DATE)
        return daily["temperature_2m_max"][idx], daily["temperature_2m_min"][idx]
    return None, None


def mean(values):
    return sum(values) / len(values)


def median(values):
    s = sorted(values)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2.0


def stdev(values):
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / len(values))


def main():
    results = []
    errors = []

    for name, endpoint in MODELS:
        try:
            high_c, low_c = fetch_forecast(endpoint)
            if high_c is None:
                errors.append(name)
                continue
            results.append((name, high_c, low_c))
        except Exception as e:
            errors.append(name)

    # Sort by high descending
    results.sort(key=lambda r: r[1], reverse=True)

    w = 64  # box width

    def hline(left, fill, mid, right):
        return left + fill * (w - 2) + right

    print(hline("╔", "═", "", "╗"))
    print(f"║{'POLYMARKET WEATHER FORECAST COMPARISON':^{w-2}}║")
    print(f"║{'City: ' + CITY + ' | Date: ' + TARGET_DATE:^{w-2}}║")
    print(hline("╠", "═", "", "╣"))

    # Table header
    print(f"║ {'Model':<13}│ {'High (°C/°F)':<17}│ {'Low (°C/°F)':<{w-37}}║")
    print(f"║{'─'*14}┼{'─'*18}┼{'─'*(w-35)}║")

    for name, high_c, low_c in results:
        high_f = c_to_f(high_c)
        low_f = c_to_f(low_c)
        high_str = f"{high_c:.1f} / {high_f:.1f}"
        low_str = f"{low_c:.1f} / {low_f:.1f}"
        print(f"║ {name:<13}│ {high_str:<17}│ {low_str:<{w-37}}║")

    for name in errors:
        print(f"║ {name:<13}│ {'unavailable':<17}│ {'unavailable':<{w-37}}║")

    if len(results) < 2:
        print(hline("╠", "═", "", "╣"))
        print(f"║{'Not enough data for consensus analysis':^{w-2}}║")
        print(hline("╚", "═", "", "╝"))
        return

    highs = [r[1] for r in results]
    m = mean(highs)
    med = median(highs)
    lo = min(highs)
    hi = max(highs)
    sd = stdev(highs)

    def row(text):
        # pad text to fill the box interior
        inner = w - 2
        # account for unicode chars that may have different display widths
        pad = inner - len(text)
        if pad < 0:
            pad = 0
        return "║" + text + " " * pad + "║"

    print(hline("╠", "═", "", "╣"))
    print(row(f"{'CONSENSUS':^{w-2}}"))
    print(row(f" Mean High:      {m:.1f}°C / {c_to_f(m):.1f}°F"))
    print(row(f" Median High:    {med:.1f}°C / {c_to_f(med):.1f}°F"))
    print(row(f" Range:          {lo:.1f} – {hi:.1f}°C"))
    print(row(f" Std Dev:        {sd:.1f}°C"))

    print(hline("╠", "═", "", "╣"))
    print(row(f"{'BETTING GUIDANCE':^{w-2}}"))

    if sd < 1.0:
        conf = "HIGH — models strongly agree"
    elif sd <= 2.0:
        conf = "MODERATE — some model disagreement"
    else:
        conf = "LOW — significant model spread, risky bet"

    print(row(f" Confidence:     {conf}"))
    print(row(f" Best estimate:  {med:.1f}°C ({c_to_f(med):.1f}°F)"))
    print(row(f" Likely bracket: {lo:.1f} – {hi:.1f}°C"))
    print(hline("╚", "═", "", "╝"))


if __name__ == "__main__":
    main()
