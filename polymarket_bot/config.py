"""
Configuration for the Polymarket Weather Trading Bot.

Edit CONTRACTS to define the markets you want to trade.
Edit STRATEGY_CONFIG to tune trading behavior.
"""

from datetime import date, timedelta

# ─── CONTRACTS TO MONITOR ────────────────────────────────────────────────────
# Each contract represents a Polymarket-style over/under temperature bet.
#   - market_yes_price: current market price for YES (0.0–1.0)
#     e.g. 0.65 means the market thinks 65% chance the temp exceeds threshold
CONTRACTS = [
    {
        "id": "london-high-2026-03-19",
        "city": "London",
        "lat": 51.5074,
        "lon": -0.1278,
        "timezone": "Europe/London",
        "target_date": (date.today() + timedelta(days=1)).isoformat(),
        "threshold_c": 15.0,
        "market_yes_price": 0.65,
        "description": "London daily high > 15°C",
    },
    {
        "id": "london-high-2026-03-20",
        "city": "London",
        "lat": 51.5074,
        "lon": -0.1278,
        "timezone": "Europe/London",
        "target_date": (date.today() + timedelta(days=2)).isoformat(),
        "threshold_c": 16.0,
        "market_yes_price": 0.55,
        "description": "London daily high > 16°C",
    },
]

# ─── STRATEGY CONFIGURATION ──────────────────────────────────────────────────
STRATEGY_CONFIG = {
    # Consensus Edge strategy: bet when our probability diverges from market
    "consensus_edge": {
        "enabled": True,
        "min_edge": 0.15,           # minimum probability edge to trigger (15%)
        "max_std_dev_c": 3.0,       # skip if model disagreement exceeds this
    },
    # High Confidence strategy: bet only when models tightly agree
    "high_confidence": {
        "enabled": True,
        "max_std_dev_c": 1.0,       # models must agree within this range
        "min_probability": 0.75,    # our estimated probability must exceed this
    },
}

# ─── TRADING PARAMETERS ──────────────────────────────────────────────────────
STAKE_PER_TRADE = 10.0          # dollars per paper trade
STARTING_BALANCE = 1000.0       # initial paper trading balance
MIN_MODELS_REQUIRED = 3         # need at least this many models to trade

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
DEFAULT_INTERVAL_MINUTES = 360  # 6 hours between scheduled runs

# ─── DATABASE ─────────────────────────────────────────────────────────────────
DB_PATH = "polymarket_bot.db"

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = 5000
