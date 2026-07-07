#!/usr/bin/env python3
"""
CLI entry point for the Polymarket Weather Trading Bot.

Usage:
    python run_bot.py discover                        # find weather markets on Polymarket
    python run_bot.py discover --city "NYC"            # search for a specific city
    python run_bot.py analyze                          # forecast analysis, no trades
    python run_bot.py trade                            # analyze + execute paper trades
    python run_bot.py settle                           # settle past trades
    python run_bot.py dashboard                        # start the web dashboard
    python run_bot.py run --interval 360               # continuous mode

Contracts are auto-discovered from Polymarket for the cities in
config.AUTO_DISCOVER_CITIES; manual contracts can be added in
config.MANUAL_CONTRACTS.
"""

import argparse
import re
import time
from datetime import date

from polymarket_bot import config
from polymarket_bot.weather import fetch_all_models, compute_consensus, c_to_f
from polymarket_bot.strategy import generate_signals, estimate_probability_over
from polymarket_bot.discovery import build_auto_contracts
from polymarket_bot.trader import (
    init_db,
    execute_trade,
    has_open_trade,
    settle_trades,
    get_balance,
    get_metrics,
    record_analysis,
)
from polymarket_bot.polymarket_api import (
    public_search,
    search_temperature_markets,
    get_event,
    get_market,
    get_live_yes_price,
    parse_market_prices,
)


def print_header():
    print()
    print("=" * 70)
    print("  POLYMARKET WEATHER TRADING BOT — Paper Trading")
    print("=" * 70)
    print()


def get_active_contracts():
    """Manual contracts plus auto-discovered Polymarket events."""
    contracts = list(config.MANUAL_CONTRACTS)
    auto = build_auto_contracts(config.AUTO_DISCOVER_CITIES,
                                max_days_ahead=config.MAX_DAYS_AHEAD)
    known_ids = {c["id"] for c in contracts}
    contracts.extend(c for c in auto if c["id"] not in known_ids)
    return contracts


# ─── MARKET PARSING ───────────────────────────────────────────────────────────

def _extract_temp_from_question(question):
    """Extract the temperature value from a Polymarket question string."""
    m = re.search(r"(-?\d+)\s*°?\s*[CF]", question)
    if m:
        return int(m.group(1))
    m = re.search(r"be\s+(-?\d+)", question)
    if m:
        return int(m.group(1))
    return None


def _parse_bracket_event(event_data):
    """
    Parse a Polymarket temperature bracket event.
    Returns (brackets, unit) where brackets is a sorted list of
    (temp, yes_price, is_lower, is_upper) and unit is 'C' or 'F'.
    """
    brackets = []
    unit = "C"
    for m in event_data.get("markets", []):
        q = m.get("question", "")
        if "°F" in q or re.search(r"\d\s*F\b", q):
            unit = "F"
        parsed = parse_market_prices(m)
        yes_p = parsed["yes_price"]
        if yes_p is None:
            yes_p = get_live_yes_price(m) or 0.0

        temp = _extract_temp_from_question(q)
        if temp is None:
            continue

        ql = q.lower()
        is_lower = "or below" in ql or "or less" in ql
        is_upper = "or higher" in ql or "or above" in ql or "or more" in ql
        brackets.append((temp, yes_p, is_lower, is_upper))

    brackets.sort(key=lambda x: x[0])
    return brackets, unit


def _market_prob_over(brackets, threshold):
    """Market-implied P(rounded high > threshold) = sum of brackets above it."""
    if not brackets:
        return None
    prob = 0.0
    for temp, yes_p, is_lower, is_upper in brackets:
        if is_upper or temp > threshold:
            prob += yes_p
    return prob


def _consensus_in_unit(consensus, unit):
    """Convert consensus °C stats into the market's native unit."""
    if unit == "C":
        return consensus["median_high"], consensus["std_high"]
    return c_to_f(consensus["median_high"]), consensus["std_high"] * 9.0 / 5.0


def _pick_best_threshold(brackets, consensus, unit):
    """
    Evaluate every bracket boundary as a "high > t" threshold and return
    (threshold, our_prob, market_prob) for the largest absolute edge.
    Skips near-resolved tails (market prob outside the configured band).
    """
    median_n, std_n = _consensus_in_unit(consensus, unit)
    best = None
    for temp, _, _, is_upper in brackets:
        if is_upper:
            continue  # "≥X" has no brackets above it
        market_p = _market_prob_over(brackets, temp)
        if market_p is None:
            continue
        if not (config.THRESHOLD_MARKET_PROB_MIN <= market_p
                <= config.THRESHOLD_MARKET_PROB_MAX):
            continue
        # Brackets resolve on rounded degrees: "high > t" means rounded >= t+1,
        # i.e. actual > t + 0.5 in continuous terms.
        our_p = estimate_probability_over(temp + 0.5, median_n, std_n)
        edge = our_p - market_p
        if best is None or abs(edge) > abs(best[3]):
            best = (temp, our_p, market_p, edge)
    if best is None:
        return None, None, None
    return best[0], best[1], best[2]


# ─── ANALYSIS PIPELINE ────────────────────────────────────────────────────────

def analyze_contract(contract, execute=False):
    """Analyze a single contract. Optionally execute paper trades."""
    contract_id = contract["id"]
    target = contract["target_date"]

    print(f"  Contract: {contract.get('description', contract_id)}")
    print(f"  City: {contract['city']} | Date: {target}")

    if target < date.today().isoformat():
        print("  [EXPIRED] Target date has passed. Run 'settle' to resolve.\n")
        return

    # 1. Market data
    brackets, unit = [], "C"
    market_yes = None
    price_source = "unavailable"

    if contract.get("event_id"):
        ev = get_event(contract["event_id"])
        if ev and ev.get("markets"):
            brackets, unit = _parse_bracket_event(ev)
            price_source = "LIVE (event)"
    if not brackets and contract.get("condition_id"):
        market_data = get_market(contract["condition_id"])
        if market_data:
            live = get_live_yes_price(market_data)
            if live and live > 0:
                market_yes, price_source = live, "LIVE"
    if not brackets and market_yes is None and contract.get("market_yes_price") is not None:
        market_yes, price_source = contract["market_yes_price"], "manual"

    if not brackets and market_yes is None:
        print("  [SKIP] No market price available.\n")
        record_analysis(contract, None, None, None, price_source, "skip:no_price")
        return

    if brackets:
        print(f"  Market brackets ({unit}°):")
        for temp, yes_p, is_lower, is_upper in brackets:
            bar = "█" * int(yes_p * 40)
            label = f"{'≤' if is_lower else '≥' if is_upper else ''}{temp}°{unit}"
            print(f"    {label:<8} {yes_p:5.1%} {bar}")
        print()

    # 2. Weather consensus
    results, errors = fetch_all_models(
        contract["lat"], contract["lon"], contract["timezone"], target
    )
    if len(results) < config.MIN_MODELS_REQUIRED:
        print(f"  [SKIP] Only {len(results)} models available "
              f"(need {config.MIN_MODELS_REQUIRED})\n")
        record_analysis(contract, None, None, market_yes, price_source, "skip:few_models")
        return

    print(f"  {'Model':<13} {'High °C':>8} {'High °F':>8}")
    print(f"  {'─'*13} {'─'*8} {'─'*8}")
    for r in sorted(results, key=lambda x: x["high_c"], reverse=True):
        print(f"  {r['model']:<13} {r['high_c']:>7.1f}  {c_to_f(r['high_c']):>7.1f}")
    for name in errors:
        print(f"  {name:<13} {'N/A':>8} {'N/A':>8}")
    print()

    consensus = compute_consensus(results)
    print(f"  Consensus: median={consensus['median_high']:.1f}°C  "
          f"std={consensus['std_high']:.1f}°C  "
          f"range={consensus['min_high']:.1f}–{consensus['max_high']:.1f}°C")

    # 3. Threshold + probabilities
    if brackets:
        threshold = contract.get("threshold_c")
        if threshold is not None:
            median_n, std_n = _consensus_in_unit(consensus, unit)
            our_prob = estimate_probability_over(threshold + 0.5, median_n, std_n)
            market_prob = _market_prob_over(brackets, threshold)
        else:
            threshold, our_prob, market_prob = _pick_best_threshold(
                brackets, consensus, unit)
            if threshold is None:
                print("  [SKIP] No tradeable bracket (market prices near 0/1 everywhere).\n")
                record_analysis(contract, consensus, None, None, price_source,
                                "skip:no_bracket")
                return
    else:
        threshold = contract["threshold_c"]
        our_prob = estimate_probability_over(
            threshold, consensus["median_high"], consensus["std_high"])
        market_prob = market_yes

    edge = our_prob - market_prob
    print(f"  Best bet: P(high > {threshold}°{unit})  |  "
          f"Models = {our_prob*100:.1f}%  |  Market = {market_prob*100:.1f}%  |  "
          f"Edge = {edge*100:+.1f}%")
    print()

    # 4. Strategy + execution
    # Strategies compare probabilities in the market's native, rounding-corrected
    # space, so feed them the adjusted threshold and native-unit consensus.
    median_n, std_n = _consensus_in_unit(consensus, unit)
    strategy_contract = {
        **contract,
        "threshold_c": threshold + 0.5 if brackets else threshold,
        "market_yes_price": market_prob,
    }
    strategy_consensus = {**consensus, "median_high": median_n, "std_high": std_n}
    signals = generate_signals(strategy_contract, strategy_consensus,
                               config.STRATEGY_CONFIG)

    decision = ("signal:" + ",".join(s["strategy"] for s in signals)
                if signals else "no_trade")
    analysis_contract = {**contract, "threshold_c": threshold}
    record_analysis(analysis_contract, consensus, our_prob, market_prob,
                    price_source, decision)

    if not signals:
        print("  [NO TRADE] No strategy triggered.\n")
        return

    trade_contract = {**contract, "threshold_c": threshold,
                      "temp_unit": unit if brackets else "C"}
    for sig in signals:
        tag = sig["strategy"].replace("_", " ").upper()
        print(f"  >> SIGNAL [{tag}]: {sig['side']} at {sig['entry_price']:.2f}  "
              f"(edge: {sig['edge']*100:.1f}%)")

        if execute:
            if has_open_trade(contract_id, sig["strategy"]):
                print("     Already have open trade for this contract+strategy. Skipping.")
            else:
                trade_id = execute_trade(sig, trade_contract)
                if trade_id:
                    print(f"     TRADE EXECUTED (id={trade_id}, "
                          f"stake=${config.STAKE_PER_TRADE:.2f})")
                else:
                    print("     INSUFFICIENT BALANCE — trade not placed.")
    print()


def _run_all_contracts(execute):
    contracts = get_active_contracts()
    if not contracts:
        print("  No contracts found. Check AUTO_DISCOVER_CITIES in config.py\n")
        return
    print(f"  {len(contracts)} contract(s) active\n")
    print("-" * 70)
    for contract in contracts:
        try:
            analyze_contract(contract, execute=execute)
        except Exception as e:
            print(f"  [ERROR] {contract['id']}: {e}\n")
        print("-" * 70)


# ─── COMMANDS ─────────────────────────────────────────────────────────────────

def cmd_discover(args):
    print_header()
    city = args.city
    query = args.query

    if query:
        print(f"  Searching Polymarket for: \"{query}\"\n")
        events = public_search(query, limit=10)
    elif city:
        print(f"  Searching for temperature markets in {city}...\n")
        events = search_temperature_markets(city=city, limit=10)
    else:
        print("  Searching for temperature markets on Polymarket...\n")
        events = search_temperature_markets(limit=10)

    open_events = [ev for ev in events if not ev.get("closed")]
    if not open_events:
        print("  No open markets found.\n")
        return

    print(f"  OPEN EVENTS ({len(open_events)}):\n")
    for ev in open_events:
        brackets, unit = _parse_bracket_event(ev)
        print(f"  Event: {ev.get('title')}  (event_id={ev.get('id')})")
        for temp, yes_p, is_lower, is_upper in brackets:
            bar = "█" * int(yes_p * 30)
            label = f"{'≤' if is_lower else '≥' if is_upper else ''}{temp}°{unit}"
            print(f"    {label:<8} {yes_p:5.1%} {bar}")
        print()

    print("  Auto-discovery already covers cities in config.AUTO_DISCOVER_CITIES.")
    print("  To pin one manually, add an entry with \"event_id\" to MANUAL_CONTRACTS.")
    print()


def cmd_analyze(args):
    init_db()
    print_header()
    _run_all_contracts(execute=False)


def cmd_trade(args):
    init_db()
    print_header()
    print(f"  Balance: ${get_balance():.2f}\n")
    _run_all_contracts(execute=True)
    print(f"\n  Balance after trading: ${get_balance():.2f}\n")


def cmd_settle(args):
    init_db()
    print_header()
    print("  Settling open trades...\n")
    settled = settle_trades()
    if not settled:
        print("  No trades to settle (either none expired or actuals unavailable).\n")
    else:
        for s in settled:
            tag = "WIN" if s["outcome"] == "win" else "LOSS"
            print(f"  Trade #{s['id']} [{s['contract_id']}]: {tag}  "
                  f"actual={s['actual_temp_c']:.1f}°C  pnl=${s['pnl']:+.2f}")
        print(f"\n  Balance: ${get_balance():.2f}\n")


def cmd_dashboard(args):
    from polymarket_bot.dashboard import run_dashboard
    print(f"\n  Starting dashboard at http://localhost:{config.DASHBOARD_PORT}\n")
    run_dashboard()


def cmd_run(args):
    init_db()
    interval = args.interval
    print_header()
    print(f"  Continuous mode: running every {interval} minutes")
    print("  Press Ctrl+C to stop.\n")
    while True:
        print(f"\n{'='*70}")
        print(f"  Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        try:
            settled = settle_trades()
        except Exception as e:
            print(f"  [WARNING] Settlement failed this run: {e}")
            settled = []
        for s in settled:
            tag = "WIN" if s["outcome"] == "win" else "LOSS"
            print(f"  Settled #{s['id']}: {tag} (pnl=${s['pnl']:+.2f})")
        if settled:
            print()
        try:
            _run_all_contracts(execute=True)
        except Exception as e:
            print(f"  [ERROR] Run failed: {e}")
        print(f"\n  Balance: ${get_balance():.2f}")
        metrics = get_metrics()
        print(f"  Total trades: {metrics['total_trades']}  "
              f"Win rate: {metrics['win_rate']*100:.0f}%  "
              f"P&L: ${metrics['total_pnl']:+.2f}")
        print(f"\n  Next run in {interval} minutes...")
        try:
            time.sleep(interval * 60)
        except KeyboardInterrupt:
            print("\n\n  Bot stopped.\n")
            break


def cmd_metrics(args):
    init_db()
    print_header()
    m = get_metrics()
    print(f"  Total trades:   {m['total_trades']}")
    print(f"  Open:           {m['open_trades']}")
    print(f"  Settled:        {m['settled_trades']}  ({m['wins']}W / {m['losses']}L)")
    print(f"  Win rate:       {m['win_rate']*100:.0f}%")
    print(f"  Total P&L:      ${m['total_pnl']:+.2f}")
    print(f"  ROI:            {m['roi']*100:.1f}%")
    print(f"  Balance:        ${m['balance']:.2f}")
    print(f"  Avg edge:       {m['avg_edge']*100:.1f}%")
    print()
    if m["by_strategy"]:
        print("  By Strategy:")
        for name, d in m["by_strategy"].items():
            print(f"    {name}: {d['trades']} trades, "
                  f"{d['win_rate']*100:.0f}% win, "
                  f"P&L ${d['pnl']:+.2f}, "
                  f"ROI {d['roi']*100:.1f}%")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Weather Trading Bot",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command")

    disc_p = sub.add_parser("discover", help="Find weather markets on Polymarket")
    disc_p.add_argument("--city", "-c", type=str, default="",
                        help="City name (e.g. 'London', 'NYC', 'Seoul')")
    disc_p.add_argument("--query", "-q", type=str, default="",
                        help="Free-text search (e.g. 'temperature May 2026')")

    sub.add_parser("analyze", help="Show forecast analysis without trading")
    sub.add_parser("trade", help="Analyze and execute paper trades")
    sub.add_parser("settle", help="Settle expired trades using observed temps")
    sub.add_parser("dashboard", help="Start the web dashboard")
    sub.add_parser("metrics", help="Show trading metrics summary")

    run_p = sub.add_parser("run", help="Continuous scheduled mode")
    run_p.add_argument(
        "--interval", type=int, default=config.DEFAULT_INTERVAL_MINUTES,
        help=f"Minutes between runs (default: {config.DEFAULT_INTERVAL_MINUTES})",
    )

    args = parser.parse_args()
    commands = {
        "discover": cmd_discover,
        "analyze": cmd_analyze,
        "trade": cmd_trade,
        "settle": cmd_settle,
        "dashboard": cmd_dashboard,
        "run": cmd_run,
        "metrics": cmd_metrics,
    }
    fn = commands.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
