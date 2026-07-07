"""
Flask web dashboard for the Polymarket Weather Trading Bot.

Runs locally with `python run_bot.py dashboard`, or on a VPS behind
gunicorn:  gunicorn -w 2 -b 0.0.0.0:5000 polymarket_bot.dashboard:app

If config.DASHBOARD_TOKEN is set (via the DASHBOARD_TOKEN env var), every
request must carry the token — either ?token=... once (stored in a cookie)
or an X-Dashboard-Token header for API calls.
"""

import os
from flask import Flask, render_template, jsonify, request, abort, make_response

from polymarket_bot import config
from polymarket_bot.trader import (
    get_metrics,
    get_all_trades,
    get_open_trades,
    get_balance_history,
    get_latest_analyses,
    get_analysis_history,
    settle_trades,
    init_db,
)

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), "templates"),
)

init_db()

_COOKIE = "dash_token"


@app.before_request
def _check_token():
    token = config.DASHBOARD_TOKEN
    if not token:
        return  # auth disabled (local use)
    if request.path == "/health":
        return  # uptime checks don't need auth
    supplied = (
        request.args.get("token")
        or request.headers.get("X-Dashboard-Token")
        or request.cookies.get(_COOKIE)
    )
    if supplied != token:
        abort(401, description="Missing or invalid token. Open /?token=YOUR_TOKEN")


@app.after_request
def _set_token_cookie(resp):
    token = config.DASHBOARD_TOKEN
    if token and request.args.get("token") == token:
        resp.set_cookie(_COOKIE, token, max_age=90 * 24 * 3600,
                        httponly=True, samesite="Lax")
    return resp


def _try_settle():
    """Settlement needs network; never let it break a page load."""
    try:
        settle_trades()
    except Exception:
        pass


@app.route("/")
def index():
    _try_settle()
    return render_template(
        "dashboard.html",
        metrics=get_metrics(),
        trades=get_all_trades(),
        open_positions=get_open_trades(),
        analyses=get_latest_analyses(),
        config=config,
    )


@app.route("/api/metrics")
def api_metrics():
    _try_settle()
    return jsonify(get_metrics())


@app.route("/api/trades")
def api_trades():
    return jsonify(get_all_trades())


@app.route("/api/balance_history")
def api_balance_history():
    return jsonify(get_balance_history())


@app.route("/api/analyses")
def api_analyses():
    return jsonify(get_latest_analyses())


@app.route("/api/analyses/history")
def api_analyses_history():
    contract_id = request.args.get("contract_id")
    return jsonify(get_analysis_history(contract_id=contract_id))


@app.route("/health")
def health():
    return jsonify({"status": "ok"})


def run_dashboard():
    app.run(
        host=config.DASHBOARD_HOST,
        port=config.DASHBOARD_PORT,
        debug=False,
    )
