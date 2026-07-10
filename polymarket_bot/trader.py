"""
Paper trading engine with SQLite persistence.

Handles trade execution, settlement (using observed temperatures),
analysis logging, and portfolio metrics.
"""

import sqlite3
from datetime import datetime, date, timezone

from polymarket_bot import config
from polymarket_bot.weather import fetch_actual_temperature


def _now():
    return datetime.now(timezone.utc).isoformat()


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
            lat REAL,
            lon REAL,
            timezone TEXT,
            temp_unit TEXT DEFAULT 'C',
            bet_type TEXT DEFAULT 'over',
            bracket_low REAL,
            event_id TEXT,
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

        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            contract_id TEXT NOT NULL,
            description TEXT,
            city TEXT,
            target_date TEXT,
            threshold_c REAL,
            model_median REAL,
            model_std REAL,
            model_min REAL,
            model_max REAL,
            model_count INTEGER,
            our_probability REAL,
            market_probability REAL,
            price_source TEXT,
            edge REAL,
            decision TEXT
        );
    """)
    # Migrate older trades tables that predate the coordinate columns
    existing = {r["name"] for r in conn.execute("PRAGMA table_info(trades)")}
    for col, typ in (("lat", "REAL"), ("lon", "REAL"), ("timezone", "TEXT"),
                     ("temp_unit", "TEXT DEFAULT 'C'"),
                     ("bet_type", "TEXT DEFAULT 'over'"),
                     ("bracket_low", "REAL"), ("event_id", "TEXT")):
        if col not in existing:
            conn.execute(f"ALTER TABLE trades ADD COLUMN {col} {typ}")

    cur = conn.execute("SELECT COUNT(*) FROM balance_history")
    if cur.fetchone()[0] == 0:
        conn.execute(
            "INSERT INTO balance_history (timestamp, balance, event) VALUES (?, ?, ?)",
            (_now(), config.STARTING_BALANCE, "initial_deposit"),
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
        (_now(), balance, event),
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
            lat, lon, timezone, temp_unit, bet_type, bracket_low, event_id,
            side, strategy, entry_price, stake, model_median, model_std,
            our_probability, market_probability, edge, status)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'open')""",
        (
            _now(),
            contract["id"],
            contract.get("description", ""),
            contract["city"],
            contract["target_date"],
            contract["threshold_c"],
            contract.get("lat"),
            contract.get("lon"),
            contract.get("timezone"),
            contract.get("temp_unit", "C"),
            contract.get("bet_type", "over"),
            contract.get("bracket_low"),
            str(contract.get("event_id") or ""),
            signal["side"],
            signal["strategy"],
            signal["entry_price"],
            stake,
            signal.get("model_median"),
            signal.get("model_std"),
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


def record_analysis(contract, consensus, our_prob, market_prob, price_source,
                    decision, db_path=None):
    """Log an analysis snapshot so the dashboard can show forecast-vs-market history."""
    conn = _get_db(db_path)
    conn.execute(
        """INSERT INTO analyses
           (timestamp, contract_id, description, city, target_date, threshold_c,
            model_median, model_std, model_min, model_max, model_count,
            our_probability, market_probability, price_source, edge, decision)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _now(),
            contract["id"],
            contract.get("description", ""),
            contract["city"],
            contract["target_date"],
            contract["threshold_c"],
            consensus["median_high"] if consensus else None,
            consensus["std_high"] if consensus else None,
            consensus["min_high"] if consensus else None,
            consensus["max_high"] if consensus else None,
            consensus["model_count"] if consensus else 0,
            our_prob,
            market_prob,
            price_source,
            (our_prob - market_prob) if (our_prob is not None and market_prob is not None) else None,
            decision,
        ),
    )
    conn.commit()
    conn.close()


def get_latest_analyses(db_path=None):
    """Most recent analysis per contract."""
    conn = _get_db(db_path)
    rows = conn.execute(
        """SELECT a.* FROM analyses a
           INNER JOIN (
               SELECT contract_id, MAX(id) AS max_id FROM analyses GROUP BY contract_id
           ) latest ON a.id = latest.max_id
           ORDER BY a.target_date"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_analysis_history(contract_id=None, limit=200, db_path=None):
    conn = _get_db(db_path)
    if contract_id:
        rows = conn.execute(
            "SELECT * FROM analyses WHERE contract_id = ? ORDER BY id DESC LIMIT ?",
            (contract_id, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM analyses ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def settle_trades(db_path=None):
    """Settle all open trades whose target_date has passed."""
    conn = _get_db(db_path)
    today = date.today().isoformat()
    open_trades = conn.execute(
        "SELECT * FROM trades WHERE status = 'open' AND target_date < ?", (today,)
    ).fetchall()

    settled = []
    for trade in open_trades:
        bet_type = (trade["bet_type"] or "over") if "bet_type" in trade.keys() else "over"
        threshold = trade["threshold_c"]
        bet_hit = None
        actual = None

        # Bracket bets settle against the market's own resolution when
        # available — that is what a real position would pay on.
        if bet_type == "bracket" and trade["event_id"]:
            resolved = _resolve_event_bracket(trade["event_id"])
            if resolved is not None:
                lo = trade["bracket_low"] if trade["bracket_low"] is not None else threshold
                bet_hit = lo <= resolved <= threshold
                actual = float(resolved)

        if bet_hit is None:
            # Fallback (and the path for over/under bets): observed weather.
            lat, lon, tz = trade["lat"], trade["lon"], trade["timezone"]
            if lat is None or lon is None or tz is None:
                contract_cfg = _find_contract(trade["contract_id"])
                if not contract_cfg:
                    continue  # can't settle without coordinates
                lat, lon, tz = (contract_cfg["lat"], contract_cfg["lon"],
                                contract_cfg["timezone"])

            actual = fetch_actual_temperature(lat, lon, tz, trade["target_date"])
            if actual is None:
                continue

            # Polymarket resolves on whole degrees in the market's native unit.
            unit = (trade["temp_unit"] or "C") if "temp_unit" in trade.keys() else "C"
            actual_native = actual * 9.0 / 5.0 + 32.0 if unit == "F" else actual
            if bet_type == "bracket":
                lo = trade["bracket_low"] if trade["bracket_low"] is not None else threshold
                bet_hit = lo <= round(actual_native) <= threshold
            else:
                bet_hit = round(actual_native) > threshold

        side = trade["side"]
        stake = trade["stake"]
        entry_price = trade["entry_price"]

        won = bet_hit if side == "YES" else not bet_hit

        if won:
            pnl = stake * (1.0 - entry_price) / entry_price
        else:
            pnl = -stake

        outcome = "win" if won else "loss"

        conn.execute(
            """UPDATE trades SET status='settled', outcome=?, actual_temp_c=?,
               pnl=?, settled_at=? WHERE id=?""",
            (outcome, actual, pnl, _now(), trade["id"]),
        )

        balance = _get_current_balance(conn)
        returned = stake + pnl if won else 0.0
        _record_balance(conn, balance + returned,
                        f"trade_settle:{trade['contract_id']}:{outcome}")

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


def _resolve_event_bracket(event_id):
    """Winning bracket temp of a resolved Polymarket event, or None."""
    try:
        from polymarket_bot.polymarket_api import get_event
        from polymarket_bot.brackets import parse_bracket_event
        ev = get_event(event_id)
        if not ev:
            return None
        brackets, _ = parse_bracket_event(ev)
        winners = [b for b in brackets if b.get("final") is not None
                   and b["final"] > 0.9]
        if len(winners) == 1:
            return winners[0]["temp"]
    except Exception:
        pass
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
