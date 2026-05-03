#!/usr/bin/env python3
"""
CLI entry point for the Polymarket Weather Trading Bot.

Usage:
    python run_bot.py discover                        # find weather markets on Polymarket
    python run_bot.py discover --city "NYC"            # search for a specific city
    python run_bot.py discover --city "London" --live  # show live CLOB prices
    python run_bot.py analyze                          # forecast analysis, no trades
    python run_bot.py trade                            # analyze + execute paper trades
    python run_bot.py settle                           # settle past trades
    python run_bot.py dashboard                        # start the web dashboard
    python run_bot.py run --interval 360               # continuous mode
"""

import argparse
import json
import re
import time
from datetime import date

from polymarket_bot import config
from polymarket_bot.weather import fetch_all_models, compute_consensus, c_to_f
from polymarket_bot.strategy import generate_signals, estimate_probability_over
from polymarket_bot.trader import (
    init_db,
    execute_trade,
    has_open_trade,
    settle_trades,
    get_balance,
    get_metrics,
)
from polymarket_bot.polymarket_api import (
    public_search,
    search_temperature_markets,
    get_live_yes_price,
    parse_market_prices,
)


def print_header():
    print()
    print("=" * 70)
    print("  POLYMARKET WEATHER TRADING BOT — Paper Trading")
    print("=" * 70)
    print()


def resolve_live_price(contract):
    """
    Resolve the market YES price for a contract.
    If event_id is set, fetches the full bracket distribution from Polymarket
    and computes P(high > threshold) from the market's own implied probabilities.
    Falls back to condition_id for a single market, then to manual price.
    Returns (price, source_label, bracket_data_or_None).
    """
    from polymarket_bot.polymarket_api import get_event, get_market

    event_id = contract.get("event_id")
    threshold = contract["threshold_c"]

    if event_id:
        ev = get_event(event_id)
        if ev and ev.get("markets"):
            brackets = _parse_bracket_event(ev)
            if brackets:
                market_prob = _market_implied_probability_over(brackets, threshold)
                if market_prob is not None:
                    return market_prob, "LIVE (event)", brackets

    cid = contract.get("condition_id")
    if cid:
        market_data = get_market(cid)
        if market_data:
            live_price = get_live_yes_price(market_data)
            if live_price and live_price > 0:
                return live_price, "LIVE", None

    manual = contract.get("market_yes_price")
    if manual is not None:
        return manual, "manual", None

    return None, "unavailable", None


def _parse_bracket_event(event_data):
    """
    Parse a Polymarket temperature bracket event into a sorted list of
    (temp_value, yes_price, is_lower_bound, is_upper_bound) tuples.
    """
    brackets = []
    for m in event_data.get("markets", []):
        q = m.get("question", "")
        parsed = parse_market_prices(m)
        yes_p = parsed["yes_price"]
        if yes_p is None:
            live = get_live_yes_price(m)
            if live:
                yes_p = live
        if yes_p is None:
            yes_p = 0.0

        temp = _extract_temp_from_question(q)
        if temp is None:
            continue

        is_lower = "or below" in q.lower() or "or less" in q.lower()
        is_upper = "or higher" in q.lower() or "or above" in q.lower() or "or more" in q.lower()
        brackets.append((temp, yes_p, is_lower, is_upper))

    brackets.sort(key=lambda x: x[0])
    return brackets


def _extract_temp_from_question(question):
    """Extract temperature value from a Polymarket question string."""
    m = re.search(r'(\d+)\s*°[CF]', question)
    if m:
        return int(m.group(1))
    m = re.search(r'be\s+(\d+)', question)
    if m:
        return int(m.group(1))
    return None


def _market_implied_probability_over(brackets, threshold_c):
    """
    From bracket probabilities, compute P(actual > threshold).
    Each bracket gives the market's probability of that exact outcome.
    P(> threshold) = sum of probabilities for all brackets above threshold.
    """
    if not brackets:
        return None
    prob_over = 0.0
    for temp, yes_p, is_lower, is_upper in brackets:
        if is_upper:
            prob_over += yes_p
        elif temp > threshold_c:
            prob_over += yes_p
        elif temp == threshold_c and not is_lower:
            pass
    return prob_over


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
    closed_events = [ev for ev in events if ev.get("closed")]

    if not open_events and not closed_events:
        print("  No markets found.\n")
        print("  Try: python run_bot.py discover --city \"London\"")
        print("       python run_bot.py discover --query \"temperature NYC\"")
        return

    if open_events:
        print(f"  OPEN EVENTS ({len(open_events)}):\n")
        for ev in open_events:
            _print_event_summary(ev, show_live=args.live)
    if closed_events:
        print(f"  RECENTLY CLOSED ({len(closed_events)}):\n")
        for ev in closed_events[:3]:
            _print_event_summary(ev, show_live=False)

    print("  ─" * 35)
    print()
    print("  To use an event, add its event_id to config.py CONTRACTS:")
    print('    "event_id": <paste event ID here>,')
    print()


def _print_event_summary(event, show_live=False):
    ev_id = event.get("id", "?")
    title = event.get("title", "?")
    markets = event.get("markets", [])

    print(f"  Event: {title}")
    print(f"  Event ID: {ev_id}  |  {len(markets)} brackets")

    if markets:
        print(f"    {'Bracket':<35} {'YES Price':>10}  Condition ID")
        print(f"    {'─'*35} {'─'*10}  {'─'*20}")

    for m in markets:
        parsed = parse_market_prices(m)
        q = m.get("question", "")
        cid = parsed["condition_id"][:20] + "..." if parsed["condition_id"] else "?"

        if show_live:
            yes_p = get_live_yes_price(m)
            source = " (live)"
        else:
            yes_p = parsed["yes_price"]
            source = ""

        price_str = f"{yes_p:.3f}{source}" if yes_p is not None else "N/A"

        temp = _extract_temp_from_question(q)
        label = f"{temp}°C" if temp else q[:30]
        if "or below" in q.lower() or "or less" in q.lower():
            label = f"≤{temp}°C"
        elif "or higher" in q.lower() or "or above" in q.lower():
            label = f"≥{temp}°C"

        print(f"    {label:<35} {price_str:>10}  {cid}")

    print()


def analyze_contract(contract, execute=False):
    """Analyze a single contract. Optionally execute paper trades."""
    contract_id = contract["id"]
    city = contract["city"]
    target = contract["target_date"]
    threshold = contract["threshold_c"]

    market_yes, price_source, brackets = resolve_live_price(contract)

    print(f"  Contract: {contract.get('description', contract_id)}")
    print(f"  City: {city} | Date: {target} | Threshold: {threshold}°C")

    if market_yes is None:
        print("  [SKIP] No market price available (set event_id or market_yes_price).\n")
        return

    print(f"  Market P(high > {threshold}°C): {market_yes:.2f} ({market_yes*100:.0f}%)  [{price_source}]")

    if brackets:
        print(f"  Market brackets:")
        for temp, yes_p, is_lower, is_upper in brackets:
            bar = "█" * int(yes_p * 40)
            label = f"{'≤' if is_lower else '≥' if is_upper else ''}{temp}°C"
            print(f"    {label:<8} {yes_p:5.1%} {bar}")
    print()

    if target < date.today().isoformat():
        print("  [EXPIRED] Target date has passed. Run 'settle' to resolve.\n")
        return

    results, errors = fetch_all_models(
        contract["lat"], contract["lon"], contract["timezone"], target
    )

    if len(results) < config.MIN_MODELS_REQUIRED:
        print(f"  [SKIP] Only {len(results)} models available "
              f"(need {config.MIN_MODELS_REQUIRED})\n")
        return

    print(f"  {'Model':<13} {'High °C':>8} {'High °F':>8}")
    print(f"  {'─'*13} {'─'*8} {'─'*8}")
    for r in sorted(results, key=lambda x: x["high_c"], reverse=True):
        print(f"  {r['model']:<13} {r['high_c']:>7.1f}  {c_to_f(r['high_c']):>7.1f}")
    if errors:
        for name in errors:
            print(f"  {name:<13} {'N/A':>8} {'N/A':>8}")
    print()

    consensus = compute_consensus(results)
    our_prob = estimate_probability_over(threshold, consensus["median_high"], consensus["std_high"])

    print(f"  Consensus: median={consensus['median_high']:.1f}°C  "
          f"std={consensus['std_high']:.1f}°C  "
          f"range={consensus['min_high']:.1f}–{consensus['max_high']:.1f}°C")
    print(f"  Our P(high > {threshold}°C) = {our_prob*100:.1f}%  |  "
          f"Market = {market_yes*100:.0f}%  |  "
          f"Edge = {(our_prob - market_yes)*100:+.1f}%")
    print()

    contract_with_price = {**contract, "market_yes_price": market_yes}
    signals = generate_signals(contract_with_price, consensus, config.STRATEGY_CONFIG)

    if not signals:
        print("  [NO TRADE] No strategy triggered.\n")
        return

    for sig in signals:
        tag = sig["strategy"].replace("_", " ").upper()
        print(f"  >> SIGNAL [{tag}]: {sig['side']} at {sig['entry_price']:.2f}  "
              f"(edge: {sig['edge']*100:.1f}%)")

        if execute:
            if has_open_trade(contract_id, sig["strategy"]):
                print(f"     Already have open trade for this contract+strategy. Skipping.")
            else:
                trade_id = execute_trade(sig, contract_with_price)
                if trade_id:
                    print(f"     TRADE EXECUTED (id={trade_id}, stake=${config.STAKE_PER_TRADE:.2f})")
                else:
                    print(f"     INSUFFICIENT BALANCE — trade not placed.")
    print()


def cmd_analyze(args):
    print_header()
    print(f"  Analyzing {len(config.CONTRACTS)} contract(s)...\n")
    print("-" * 70)
    for contract in config.CONTRACTS:
        analyze_contract(contract, execute=False)
        print("-" * 70)


def cmd_trade(args):
    init_db()
    print_header()
    balance = get_balance()
    print(f"  Balance: ${balance:.2f}\n")
    print(f"  Analyzing {len(config.CONTRACTS)} contract(s) and placing trades...\n")
    print("-" * 70)
    for contract in config.CONTRACTS:
        analyze_contract(contract, execute=True)
        print("-" * 70)
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
    init_db()
    from polymarket_bot.dashboard import run_dashboard
    print(f"\n  Starting dashboard at http://localhost:{config.DASHBOARD_PORT}\n")
    run_dashboard()


def cmd_run(args):
    init_db()
    interval = args.interval
    print_header()
    print(f"  Continuous mode: running every {interval} minutes")
    print(f"  Press Ctrl+C to stop.\n")
    while True:
        print(f"\n{'='*70}")
        print(f"  Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*70}\n")
        settled = settle_trades()
        for s in settled:
            tag = "WIN" if s["outcome"] == "win" else "LOSS"
            print(f"  Settled #{s['id']}: {tag} (pnl=${s['pnl']:+.2f})")
        if settled:
            print()
        for contract in config.CONTRACTS:
            analyze_contract(contract, execute=True)
            print("-" * 70)
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
    disc_p.add_argument("--live", action="store_true",
                        help="Fetch live CLOB prices (slower but accurate)")

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
