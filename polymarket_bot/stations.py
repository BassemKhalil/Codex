"""
Resolution-station handling.

Polymarket temperature markets resolve on a specific Wunderground station
named in each market's description (e.g. London City Airport / EGLC).
Forecasting the station's coordinates instead of a generic city point
removes the seasonal grid-vs-station bias that broke July 2026
(see backtest/EDGE_COMPARISON.md).
"""

import re

# ICAO / Wunderground station code -> (lat, lon)
STATION_COORDS = {
    # London
    "EGLC": (51.5053, 0.0553),    # London City Airport (current resolution source)
    "EGLL": (51.4700, -0.4543),   # Heathrow
    # New York
    "KLGA": (40.7769, -73.8740),  # LaGuardia
    "KJFK": (40.6413, -73.7781),
    "KNYC": (40.7789, -73.9692),  # Central Park
    # Seoul
    "RKSS": (37.5583, 126.7906),  # Gimpo
    "RKSI": (37.4602, 126.4407),  # Incheon
    # Others seen on Polymarket weather
    "VHHH": (22.3080, 113.9185),  # Hong Kong Intl
    "DNMM": (6.5774, 3.3212),     # Lagos
    "UUEE": (55.9736, 37.4125),   # Moscow Sheremetyevo
    "EPWA": (52.1657, 20.9671),   # Warsaw Chopin
}

_WU_URL = re.compile(
    r"wunderground\.com/history/daily/[A-Za-z0-9/_-]*?/([A-Za-z0-9]{3,5})\b")


def station_from_text(text):
    """Extract the station code from a market description, or None."""
    if not text:
        return None
    m = _WU_URL.search(text)
    if m:
        return m.group(1).upper()
    return None


def resolve_station(event_data):
    """
    -> (code, lat, lon) for the event's resolution station, or None.
    Scans market descriptions for the Wunderground URL.
    """
    for mkt in event_data.get("markets", []):
        code = station_from_text(mkt.get("description", ""))
        if code:
            coords = STATION_COORDS.get(code)
            if coords:
                return code, coords[0], coords[1]
            return code, None, None
    return None
