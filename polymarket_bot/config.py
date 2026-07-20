"""
Configuration for the Polymarket Weather Trading Bot.

The bot AUTO-DISCOVERS open "Highest temperature in {city}" events on
Polymarket for each city in AUTO_DISCOVER_CITIES — no manual contract
maintenance needed. The trading threshold is chosen per event as the
bracket boundary with the largest model-vs-market edge.

You can still pin manual contracts in MANUAL_CONTRACTS (same shape,
with "event_id" / "condition_id" / "market_yes_price" price sources).
"""

import os
from datetime import date, timedelta

# ─── CITIES TO AUTO-DISCOVER ─────────────────────────────────────────────────
# The bot searches Polymarket for open daily-high events for these cities.
# Coordinates are used for the weather-model consensus and settlement.
AUTO_DISCOVER_CITIES = [
    {"city": "London", "lat": 51.5074, "lon": -0.1278, "timezone": "Europe/London"},
    # {"city": "Seoul",  "lat": 37.5665, "lon": 126.9780, "timezone": "Asia/Seoul"},
    # {"city": "NYC",    "lat": 40.7128, "lon": -74.0060, "timezone": "America/New_York"},
]

# Only trade events up to this many days out (forecasts degrade quickly)
MAX_DAYS_AHEAD = 3

# ─── MANUAL CONTRACTS (optional) ─────────────────────────────────────────────
MANUAL_CONTRACTS = []

# Kept for backward compatibility with older imports; the bot now combines
# manual + auto-discovered contracts at runtime.
CONTRACTS = MANUAL_CONTRACTS

# ─── STRATEGY CONFIGURATION ──────────────────────────────────────────────────
#
# open_window (primary, backtested): buy the model's modal bracket in the
# first days of a market's life, only when its price is at or below the
# model's historical exact-bracket hit rate for that city and lead time.
# Backtest (Feb-Jul 2026, London+Seoul): +16.7% ROI over 177 trades.
#
# The legacy over/under strategies are kept but DISABLED: replayed at
# ~breakeven and the max-edge threshold pick is adverse selection
# (see backtest/MODEL_SKILL_REPORT.md).
STRATEGY_CONFIG = {
    "open_window": {
        "enabled": True,
        "min_lead_days": 2,         # never trade the day before / same day
        "max_lead_days": 3,
        "entry_margin": 0.0,        # ceiling = hit_rate - margin
        "min_price": 0.04,          # skip dust-priced brackets
        "require_model_ev": True,   # never pay above the model's own P(bracket)
        # historical exact-bracket hit rate of the ensemble median,
        # per city (lowercase) and lead in days — from backtest/model_skill.py
        "hit_rates": {
            "london": {1: 0.50, 2: 0.455, 3: 0.40},
            "seoul": {1: 0.37, 2: 0.34, 3: 0.28},
            "nyc": {1: 0.30, 2: 0.23, 3: 0.19},
        },
    },
    "consensus_edge": {
        "enabled": False,
        "min_edge": 0.15,
        "max_std_dev_c": 3.0,
    },
    "high_confidence": {
        "enabled": False,
        "max_std_dev_c": 1.0,
        "min_probability": 0.75,
    },
}

# Ignore brackets whose market probability is outside this band when picking
# a threshold (near-resolved tails have no meaningful liquidity/payoff).
THRESHOLD_MARKET_PROB_MIN = 0.03
THRESHOLD_MARKET_PROB_MAX = 0.97

# ─── TRADING PARAMETERS ──────────────────────────────────────────────────────
STAKE_PER_TRADE = 10.0
STARTING_BALANCE = 1000.0
MIN_MODELS_REQUIRED = 3

# Pause new trades after a losing streak (analysis continues while halted).
CIRCUIT_BREAKER = {
    "enabled": True,
    "max_consecutive_losses": 5,
    "cooldown_days": 7,
}

# ─── SCHEDULER ────────────────────────────────────────────────────────────────
# Shorter interval so newly created markets (the open window) are caught
# within a few hours of listing.
DEFAULT_INTERVAL_MINUTES = 180

# ─── DATABASE ─────────────────────────────────────────────────────────────────
# On the VPS this resolves inside /opt/polymarket-bot (the service WorkingDirectory)
DB_PATH = os.environ.get("BOT_DB_PATH", "polymarket_bot.db")

# ─── DASHBOARD ────────────────────────────────────────────────────────────────
DASHBOARD_HOST = "0.0.0.0"
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5000"))

# Access token for the dashboard. REQUIRED when exposing it on a public VPS.
# Set via environment:  export DASHBOARD_TOKEN="something-long-and-random"
# Then open:  http://your-vps:5000/?token=something-long-and-random
# (the token is remembered in a cookie after the first visit)
DASHBOARD_TOKEN = os.environ.get("DASHBOARD_TOKEN", "")
