"""
Auto-discovery of Polymarket daily temperature events.

Instead of hardcoding contracts (which go stale as markets resolve daily),
the bot searches Polymarket for open "Highest temperature in {city}" events
and builds contracts on the fly. The threshold is chosen at analysis time as
the bracket boundary with the largest model-vs-market edge.
"""

import re
from datetime import date

from polymarket_bot.polymarket_api import search_temperature_markets, get_event
from polymarket_bot.stations import resolve_station

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11,
    "december": 12,
}


def parse_date_from_slug(slug):
    """'highest-temperature-in-london-on-may-4-2026' -> date(2026, 5, 4)"""
    m = re.search(r"on-([a-z]+)-(\d{1,2})-(\d{4})$", slug or "")
    if not m:
        return None
    month = _MONTHS.get(m.group(1))
    if not month:
        return None
    try:
        return date(int(m.group(3)), month, int(m.group(2)))
    except ValueError:
        return None


def build_auto_contracts(cities, max_days_ahead=3):
    """
    Search Polymarket for open daily-high temperature events for each city
    and return contract dicts compatible with analyze_contract().

    `cities` is a list of dicts: {"city", "lat", "lon", "timezone"}.
    threshold_c is left as None — the analyzer picks the best bracket edge.
    """
    contracts = []
    today = date.today()

    for city_cfg in cities:
        city = city_cfg["city"]
        try:
            events = search_temperature_markets(city=city, limit=10)
        except Exception:
            continue

        for ev in events:
            if ev.get("closed"):
                continue
            title = (ev.get("title") or "").lower()
            if "highest temperature" not in title or city.lower() not in title:
                continue

            target = parse_date_from_slug(ev.get("slug", ""))
            if target is None or target < today:
                continue
            if (target - today).days > max_days_ahead:
                continue

            # Forecast the RESOLUTION STATION, not the generic city point
            # (see backtest/EDGE_COMPARISON.md — this was the July failure).
            lat, lon = city_cfg["lat"], city_cfg["lon"]
            station = None
            info = resolve_station(ev)
            if info is None and ev.get("id"):
                full = get_event(ev["id"])
                if full:
                    info = resolve_station(full)
            if info:
                code, s_lat, s_lon = info
                station = code
                if s_lat is not None:
                    lat, lon = s_lat, s_lon

            contracts.append({
                "id": f"{city.lower().replace(' ', '-')}-high-{target.isoformat()}",
                "city": city,
                "lat": lat,
                "lon": lon,
                "station": station,
                "timezone": city_cfg["timezone"],
                "target_date": target.isoformat(),
                "threshold_c": None,          # auto-picked from brackets
                "event_id": ev.get("id"),
                "description": (ev.get("title") or "") +
                               (f" @ {station}" if station else ""),
            })

    # Sort by date so output reads chronologically
    contracts.sort(key=lambda c: c["target_date"])
    return contracts
