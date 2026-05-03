"""
Configuration for the Polymarket Weather Trading Bot.

Edit CONTRACTS to define the markets you want to trade.
Edit STRATEGY_CONFIG to tune trading behavior.

Price discovery modes (in priority order):
  1. event_id   — fetches all brackets from a Polymarket event, computes
                   P(high > threshold) from the market's own distribution.
  2. condition_id — fetches YES price for a single binary market.
  3. market_yes_price — manual fallback (0.0-1.0).

Run `python run_bot.py discover --city "London"` to find event IDs.
"""

from datetime import date, timedelta

# ─── CONTRACTS TO MONITOR ────────────────────────────────────────────────────
CONTRACTS = [
    {
        "id": "london-high-may4",
        "city": "London",
        "lat": 51.5074,
        "lon": -0.1278,
        "timezone": "Europe/London",
        "target_date": "2026-05-04",
        "threshold_c": 18.0,
        "event_id": 439940,
        "market_yes_price": 0.55,
        "description": "London daily high > 18°C (May 4)",
    },
    {
        "id": "london-high-may5",
        "city": "London",
        "lat": 51.5074,
        "lon": -0.1278,
        "timezone": "Europe/London",
        "target_date": "2026-05-05",
        "threshold_c": 16.0,
        "event_id": 443298,
        "market_yes_price": 0.55,
        "description": "London daily high > 16°C (May 5)",
    },
]

# ─── STRATEGY CONFIGURATION ──────────────────────────────────────────────────
STRATEGY_CONFIG = {
    "consensus_edge": {
        "enabled": True,
        "min_edge": 0.15,
        "max_std_dev_c": 3.0,
    },
    "high_confidence": {
        "enabled": True,
        "max_std_dev_c": 1.0,
        "min_probability": 0.75,
    },
}

# ─── TRADING PARAMETERS ──────────────────────────────────────────────────────
STAKE_PER_TRADE = 10.0
STARTING_BALANCE = 1000.0
MIN_MODELS_REQUIRED = 3

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
DEFAULT_INTERVAL_MINUTES = 360

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = "polymarket_bot.db"

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
