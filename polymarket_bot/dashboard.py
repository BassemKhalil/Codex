"""
Flask web dashboard for the Polymarket Weather Trading Bot.
"""

import os
from flask import Flask, render_template, jsonify

from polymarket_bot import config
from polymarket_bot.trader import (
    get_metrics,
    get_all_trades,
    get_open_trades,
    get_balance_history,
    settle_trades,
    init_db,
)

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)


@app.before_request
def _ensure_db():
    init_db()


@app.route("/")
def index():
    settle_trades()
    metrics = get_metrics()
    trades = get_all_trades()
    open_pos = get_open_trades()
    return render_template(
        "dashboard.html",
        metrics=metrics,
        trades=trades,
        open_positions=open_pos,
        config=config,
    )


@app.route("/api/metrics")
def api_metrics():
    settle_trades()
    return jsonify(get_metrics())


@app.route("/api/trades")
def api_trades():
    return jsonify(get_all_trades())


@app.route("/api/balance_history")
def api_balance_history():
    return jsonify(get_balance_history())


def run_dashboard():
    init_db()
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=False,
    )
