#!/usr/bin/env python3
"""
CLI entry point for the Polymarket Weather Trading Bot.

Usage:
    python run_bot.py analyze              # show forecast analysis, no trades
    python run_bot.py trade                # analyze + execute paper trades
    python run_bot.py settle               # settle past trades using observed temps
    python run_bot.py dashboard            # start the web dashboard
    python run_bot.py run --interval 360   # continuous mode (minutes between runs)
"""

import argparse
import sys
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


def print_header():
    print()
    print("=" * 66)
    print("  POLYMARKET WEATHER TRADING BOT — Paper Trading")
    print("=" * 66)
    print()


def analyze_contract(contract, execute=False):
    """Analyze a single contract. Optionally execute paper trades."""
    cid = contract["id"]
    city = contract["city"]
    target = contract["target_date"]
    threshold = contract["threshold_c"]
    market_yes = contract["market_yes_price"]

    print(f"  Contract: {contract.get('description', cid)}")
    print(f"  City: {city} | Date: {target} | Threshold: {threshold}°C")
    print(f"  Market YES price: {market_yes:.2f} ({market_yes*100:.0f}% implied)")
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

    # Print model forecasts
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

    # Generate strategy signals
    signals = generate_signals(contract, consensus, config.STRATEGY_CONFIG)

    if not signals:
        print("  [NO TRADE] No strategy triggered.\n")
        return

    for sig in signals:
        tag = sig["strategy"].replace("_", " ").upper()
        print(f"  >> SIGNAL [{tag}]: {sig['side']} at {sig['entry_price']:.2f}  "
              f"(edge: {sig['edge']*100:.1f}%)")

        if execute:
            if has_open_trade(cid, sig["strategy"]):
                print(f"     Already have open trade for this contract+strategy. Skipping.")
            else:
                trade_id = execute_trade(sig, contract)
                if trade_id:
                    print(f"     TRADE EXECUTED (id={trade_id}, stake=${config.STAKE_PER_TRADE:.2f})")
                else:
                    print(f"     INSUFFICIENT BALANCE — trade not placed.")
    print()


def cmd_analyze(args):
    print_header()
    print(f"  Analyzing {len(config.CONTRACTS)} contract(s)...\n")
    print("-" * 66)
    for contract in config.CONTRACTS:
        analyze_contract(contract, execute=False)
        print("-" * 66)


def cmd_trade(args):
    init_db()
    print_header()
    balance = get_balance()
    print(f"  Balance: ${balance:.2f}\n")
    print(f"  Analyzing {len(config.CONTRACTS)} contract(s) and placing trades...\n")
    print("-" * 66)
    for contract in config.CONTRACTS:
        analyze_contract(contract, execute=True)
        print("-" * 66)
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
    print(f"  Continuous mode: running every {interval} minutes\n")
    print(f"  Press Ctrl+C to stop.\n")
    while True:
        print(f"\n{'='*66}")
        print(f"  Run at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*66}\n")
        settled = settle_trades()
        for s in settled:
            tag = "WIN" if s["outcome"] == "win" else "LOSS"
            print(f"  Settled #{s['id']}: {tag} (pnl=${s['pnl']:+.2f})")
        if settled:
            print()
        for contract in config.CONTRACTS:
            analyze_contract(contract, execute=True)
            print("-" * 66)
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
