"""
Polymarket API client for fetching live market data.

Uses two public APIs (no auth required for read-only):
  - Gamma API: market/event discovery and metadata
  - CLOB API: live prices, order books, price history
"""

try:
    import requests as _req

    def _get(url, params=None, timeout=10):
        resp = _req.get(url, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()
except ImportError:
    import urllib.request
    import urllib.parse
    import json as _json

    def _get(url, params=None, timeout=10):
        if params:
            url = url + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return _json.loads(resp.read().decode())

import json

GAMMA_BASE = "https://gamma-api.polymarket.com"
CLOB_BASE = "https://clob.polymarket.com"


def public_search(query, limit=10):
    """Text search across all Polymarket events. Returns list of events with nested markets."""
    try:
        data = _get(f"{GAMMA_BASE}/public-search", params={"q": query, "limit": limit})
        return data.get("events", [])
    except Exception as e:
        print(f"  [WARNING] Search failed: {e}")
        return []


def search_temperature_markets(city=None, limit=10):
    """Find temperature markets, optionally filtered by city."""
    query = f"highest temperature {city}" if city else "highest temperature"
    return public_search(query, limit=limit)


def get_event(event_id):
    """Get a specific event with all its markets."""
    try:
        return _get(f"{GAMMA_BASE}/events/{event_id}")
    except Exception as e:
        print(f"  [WARNING] Failed to fetch event {event_id}: {e}")
        return None


def get_market(condition_id):
    """Get market metadata from Gamma API."""
    try:
        return _get(f"{GAMMA_BASE}/markets/{condition_id}")
    except Exception as e:
        print(f"  [WARNING] Failed to fetch market {condition_id}: {e}")
        return None


def get_midpoint(token_id):
    """Get live midpoint price for a token from the CLOB."""
    try:
        data = _get(f"{CLOB_BASE}/midpoint", params={"token_id": token_id})
        return float(data.get("mid", 0))
    except Exception:
        return None


def get_price(token_id, side="buy"):
    """Get live price for a specific side (buy/sell) from the CLOB."""
    try:
        data = _get(f"{CLOB_BASE}/price", params={"token_id": token_id, "side": side})
        return float(data.get("price", 0))
    except Exception:
        return None


def get_orderbook(token_id):
    """Get the full order book for a token."""
    try:
        return _get(f"{CLOB_BASE}/book", params={"token_id": token_id})
    except Exception:
        return None


def get_price_history(token_id, interval="1w", fidelity=60):
    """Get historical prices for a token."""
    try:
        return _get(
            f"{CLOB_BASE}/prices-history",
            params={"market": token_id, "interval": interval, "fidelity": fidelity},
        )
    except Exception:
        return None


def parse_market_prices(market_data):
    """
    Extract YES/NO prices and token IDs from Gamma market data.
    Returns dict with yes_price, no_price, yes_token_id, no_token_id, question, condition_id.
    """
    result = {
        "yes_price": None,
        "no_price": None,
        "yes_token_id": None,
        "no_token_id": None,
        "question": market_data.get("question", ""),
        "condition_id": market_data.get("conditionId", market_data.get("condition_id", "")),
        "group_title": market_data.get("groupItemTitle", ""),
    }

    outcome_prices = market_data.get("outcomePrices")
    if outcome_prices:
        if isinstance(outcome_prices, str):
            prices = json.loads(outcome_prices)
        else:
            prices = outcome_prices
        if len(prices) >= 2:
            result["yes_price"] = float(prices[0])
            result["no_price"] = float(prices[1])

    tokens = market_data.get("clobTokenIds")
    if tokens:
        if isinstance(tokens, str):
            tokens = json.loads(tokens)
        if len(tokens) >= 2:
            result["yes_token_id"] = tokens[0]
            result["no_token_id"] = tokens[1]

    return result


def get_live_yes_price(market_data):
    """
    Get the best available live YES price for a market.
    Tries CLOB midpoint first, falls back to Gamma cached price.
    """
    parsed = parse_market_prices(market_data)

    if parsed["yes_token_id"]:
        mid = get_midpoint(parsed["yes_token_id"])
        if mid and mid > 0:
            return mid

    if parsed["yes_price"] and parsed["yes_price"] > 0:
        return parsed["yes_price"]

    return None


def get_event_with_live_prices(event_id):
    """
    Fetch an event and enrich each market with live CLOB prices.
    Returns the event dict with each market having 'live_yes_price' added.
    """
    ev = get_event(event_id)
    if not ev:
        return None
    for m in ev.get("markets", []):
        m["live_yes_price"] = get_live_yes_price(m)
    return ev
