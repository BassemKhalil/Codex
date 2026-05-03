"""
Paper trading engine with SQLite persistence.

Handles trade execution, settlement (using observed temperatures),
and portfolio metrics.
"""

import sqlite3
from datetime import datetime, date

from polymarket_bot import config
from polymarket_bot.weather import fetch_actual_temperature


def _get_db(db_path=None):
    conn = sqlite3.connect(db_path or config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path=None):
    conn = _get_db(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS trades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            contract_id TEXT NOT NULL,
            description TEXT,
            city TEXT,
            target_date TEXT,
            threshold_c REAL,
            side TEXT NOT NULL,
            strategy TEXT NOT NULL,
            entry_price REAL NOT NULL,
            stake REAL NOT NULL,
            model_median REAL,
            model_std REAL,
            our_probability REAL,
            market_probability REAL,
            edge REAL,
            status TEXT NOT NULL DEFAULT 'open',
            outcome TEXT,
            actual_temp_c REAL,
            pnl REAL,
            settled_at TEXT
        );

        CREATE TABLE IF NOT EXISTS balance_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            balance REAL NOT NULL,
            event TEXT
        );
    """)
    # Seed starting balance if empty
    cur = conn.execute("SELECT COUNT(*) FROM balance_history")
    if cur.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO balance_history (timestamp, balance, event) VALUES (?, ?, ?)",
            (datetime.utcnow().isoformat(), config.STARTING_BALANCE, "initial_deposit"),
        )
    conn.commit()
    conn.close()


def get_balance(db_path=None):
    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT balance FROM balance_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    return row["balance"] if row else config.STARTING_BALANCE


def _record_balance(conn, balance, event):
    conn.execute(
        "INSERT INTO balance_history (timestamp, balance, event) VALUES (?, ?, ?)",
        (datetime.utcnow().isoformat(), balance, event),
    )


def execute_trade(signal, contract, db_path=None):
    """Execute a paper trade from a strategy signal. Returns the trade row id."""
    conn = _get_db(db_path)
    balance = get_balance(db_path)
    stake = config.STAKE_PER_TRADE

    if stake > balance:
        conn.close()
        return None

    new_balance = balance - stake
    _record_balance(conn, new_balance, f"trade_open:{contract['id']}")

    cur = conn.execute(
        """INSERT INTO trades
           (timestamp, contract_id, description, city, target_date, threshold_c,
            side, strategy, entry_price, stake, model_median, model_std,
            our_probability, market_probability, edge, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
        (
            datetime.utcnow().isoformat(),
            contract["id"],
            contract.get("description", ""),
            contract["city"],
            contract["target_date"],
            contract["threshold_c"],
            signal["side"],
            signal["strategy"],
            signal["entry_price"],
            stake,
            signal["model_median"],
            signal["model_std"],
            signal["our_probability"],
            signal["market_probability"],
            signal["edge"],
        ),
    )
    trade_id = cur.lastrowid
    conn.commit()
    conn.close()
    return trade_id


def has_open_trade(contract_id, strategy, db_path=None):
    """Check if there's already an open trade for this contract+strategy."""
    conn = _get_db(db_path)
    row = conn.execute(
        "SELECT id FROM trades WHERE contract_id = ? AND strategy = ? AND status = 'open'",
        (contract_id, strategy),
    ).fetchone()
    conn.close()
    return row is not None


def settle_trades(db_path=None):
    """Settle all open trades whose target_date has passed."""
    conn = _get_db(db_path)
    today = date.today().isoformat()
    open_trades = conn.execute(
        "SELECT * FROM trades WHERE status = 'open' AND target_date < ?", (today,)
    ).fetchall()

    settled = []
    for trade in open_trades:
        contract_cfg = _find_contract(trade["contract_id"])
        lat = contract_cfg["lat"] if contract_cfg else 51.5074
        lon = contract_cfg["lon"] if contract_cfg else -0.1278
        tz = contract_cfg["timezone"] if contract_cfg else "Europe/London"

        actual = fetch_actual_temperature(lat, lon, tz, trade["target_date"])
        if actual is None:
            continue

        threshold = trade["threshold_c"]
        temp_exceeded = actual > threshold
        side = trade["side"]
        stake = trade["stake"]
        entry_price = trade["entry_price"]

        if side == "YES":
            won = temp_exceeded
        else:
            won = not temp_exceeded

        if won:
            pnl = stake * (1.0 - entry_price) / entry_price
        else:
            pnl = -stake

        outcome = "win" if won else "loss"
        now = datetime.utcnow().isoformat()

        conn.execute(
            """UPDATE trades SET status='settled', outcome=?, actual_temp_c=?,
               pnl=?, settled_at=? WHERE id=?""",
            (outcome, actual, pnl, now, trade["id"]),
        )

        balance = _get_current_balance(conn)
        if won:
            returned = stake + pnl
        else:
            returned = 0.0
        new_balance = balance + returned
        _record_balance(conn, new_balance, f"trade_settle:{trade['contract_id']}:{outcome}")

        settled.append({
            "id": trade["id"],
            "contract_id": trade["contract_id"],
            "outcome": outcome,
            "actual_temp_c": actual,
            "pnl": pnl,
        })

    conn.commit()
    conn.close()
    return settled


def _get_current_balance(conn):
    row = conn.execute(
        "SELECT balance FROM balance_history ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return row["balance"] if row else config.STARTING_BALANCE


def _find_contract(contract_id):
    for c in config.CONTRACTS:
        if c["id"] == contract_id:
            return c
    return None


# ─── METRICS ──────────────────────────────────────────────────────────────────

def get_all_trades(db_path=None):
    conn = _get_db(db_path)
    rows = conn.execute("SELECT * FROM trades ORDER BY timestamp DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_open_trades(db_path=None):
    conn = _get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM trades WHERE status = 'open' ORDER BY target_date"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_settled_trades(db_path=None):
    conn = _get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM trades WHERE status = 'settled' ORDER BY settled_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_balance_history(db_path=None):
    conn = _get_db(db_path)
    rows = conn.execute(
        "SELECT * FROM balance_history ORDER BY id"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_metrics(db_path=None):
    """Compute aggregate trading metrics."""
    all_trades = get_all_trades(db_path)
    settled = [t for t in all_trades if t["status"] == "settled"]
    open_trades = [t for t in all_trades if t["status"] == "open"]
    wins = [t for t in settled if t["outcome"] == "win"]
    losses = [t for t in settled if t["outcome"] == "loss"]

    total_pnl = sum(t["pnl"] for t in settled)
    total_staked = sum(t["stake"] for t in settled) if settled else 0

    by_strategy = {}
    for t in settled:
        s = t["strategy"]
        if s not in by_strategy:
            by_strategy[s] = {"trades": 0, "wins": 0, "pnl": 0.0, "staked": 0.0}
        by_strategy[s]["trades"] += 1
        by_strategy[s]["pnl"] += t["pnl"]
        by_strategy[s]["staked"] += t["stake"]
        if t["outcome"] == "win":
            by_strategy[s]["wins"] += 1

    for s in by_strategy:
        d = by_strategy[s]
        d["win_rate"] = d["wins"] / d["trades"] if d["trades"] else 0
        d["roi"] = d["pnl"] / d["staked"] if d["staked"] else 0

    return {
        "total_trades": len(all_trades),
        "open_trades": len(open_trades),
        "settled_trades": len(settled),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate": len(wins) / len(settled) if settled else 0,
        "total_pnl": total_pnl,
        "roi": total_pnl / total_staked if total_staked else 0,
        "balance": get_balance(db_path),
        "avg_edge": (
            sum(t["edge"] for t in all_trades) / len(all_trades) if all_trades else 0
        ),
        "by_strategy": by_strategy,
    }
