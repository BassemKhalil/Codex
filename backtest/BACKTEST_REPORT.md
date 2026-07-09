# Backtest Report — Polymarket Weather Trading Strategy

**Date:** 2026-07-09 · **Verdict: the current approach has negative expectancy and should not go live in its present form.**

---

## 1. What was tested

Two questions, two datasets:

| Component | Question | Data |
|---|---|---|
| **A. Forecast calibration** | Are our model-ensemble probabilities correct? | 884 days of *as-issued* day-ahead forecasts (Open-Meteo previous-runs archive, 5–6 models) vs observed highs, London, Mar 2024 → Jul 2026. GFS+JMA-only data extends to 2021. |
| **B. Strategy replay** | Would the deployed bot have made money? | Every resolved Polymarket daily-high event for **London, NYC, Seoul** since the markets began (Feb 2026): 453 events, 441 scored, with full hourly CLOB price history. The replay executes the live bot's *exact* rules (max-edge bracket pick, both strategies, $10 stakes) at a realistic decision time (midnight before the day, using only the previous day's forecasts). |

Note: Polymarket daily-temperature markets **did not exist before February 2026**, so a multi-year *market* replay is impossible for anyone. The multi-year component is the forecast-calibration study — which is the input the whole strategy stands on.

---

## 2. Finding 1 — our forecasts are good, and honestly calibrated

London, day-ahead, 5+ model era (884 days):

- Median-of-models error: **MAE 0.56 °C**, RMSE 0.75 °C, bias +0.03 °C
- Ensemble spread ≈ true error spread: **overconfidence ratio 0.90** (spread 0.84 vs residual σ 0.75 — very slightly *under*confident)
- Probability quality: **Brier 0.059** across ±3 °C thresholds; raw ensemble spread beats every inflated-σ variant tested

**The probability model is not the problem.** My pre-backtest hypothesis (σ from 5 models underestimates uncertainty) is refuted — inflating σ makes calibration *worse*.

## 3. Finding 2 — the market is *better*, and our trade selection guarantees we meet it at its best

Head-to-head on the exact thresholds the bot chooses to trade (441 events):

| Predictor | Brier score (lower = better) |
|---|---|
| Polymarket price at decision time | **0.139** |
| Our ensemble probability | 0.526 |

Our model is well-calibrated *on average* but **worse than a coin flip on the specific thresholds where it disagrees most with the market**. That is not a paradox — it is adverse selection: picking the bracket with maximum |model − market| systematically selects the cases where the market knows something we don't (fresher model runs, real-time station observations, the exact resolution station's microclimate vs our grid point). This is the winner's curse, and the strategy design maximizes exposure to it.

## 4. Finding 3 — the deployed config loses money

Replay of the **live config** (441 events, 504 trades):

- Win rate **29.4%**, P&L **−$402**, ROI **−8.0%**
- The losses concentrate exactly where the "edge" looks biggest: cheap longshots (entry < $0.15) → **210 trades, 7% win rate, −$520**
- NYC is worst (13% win rate, −$434); London mildly positive (+$222); Seoul negative (−$190)
- Your live result (0W/2L, −$20) is exactly what this distribution predicts

## 5. Finding 4 — every "profitable" variant is a lottery artifact

| Config | Trades | P&L | P&L w/o top-5 wins | P&L w/o top-10 |
|---|---|---|---|---|
| Live config | 504 | −$402 | −$1,067 | −$1,520 |
| σ ×2.0 | 298 | +$262 | −$620 | −$1,198 |
| σ ×2 + floor 1.8, edge ≥0.25 | 233 | +$347 | −$535 | −$1,111 |
| Decide 09:00 same day | 493 | +$1,563 | +$368 | −$316 |

Every configuration's profit lives in its five best longshot fills; February 2026 alone carries all of them (markets were young and soft then — +$650–800 in Feb, deep red in March and May). No parameter setting produces a *robust* edge. The 09:00 same-day result additionally rides stale last-trade prices in thin morning books that a real $10 order would move — it is not executable profit.

One honest nuance: the high-probability band (entry ≥ $0.50, where we *agree* with the market) won 73% and ran ≈ +8% ROI — statistically weak (106 trades) but consistent with "roughly fair prices minus adverse selection."

## 6. Why the market beats a 6-model ensemble

1. **Information timing** — by the evening before, the market has absorbed the 12z/18z model runs *and* human forecaster products; overnight and same-day it absorbs actual station observations. Our bot reads the same public models a few hours later at best.
2. **Resolution-source specificity** — contracts resolve on one Weather Underground station. Traders model *that station*; we forecast a lat/lon grid cell. On the tails (where max-edge sends us) a 0.5 °C systematic gap flips brackets.
3. **Selection effect** — even a well-calibrated model, forced to trade only its biggest disagreements against a better-informed counterparty, converts calibration into losses.

## 7. Recommendations

**Do (cheap, safe):**
1. **Stay in paper mode.** Do not fund this strategy as-is.
2. **Kill the max-|edge| bracket picker** — it is an adverse-selection machine. If the bot keeps trading at all, cap entries to $0.25–0.75 (avoid tails) and treat the market price as the prior.
3. Keep the bot + dashboard running as **infrastructure** — the plumbing (discovery, execution, settlement, analytics) is solid and reusable.

**Explore (where a real edge could exist):**
4. **Latency on model releases** — new model runs land at fixed times (ECMWF ~07:00/19:00 UTC, GFS every 6 h). A bot that re-prices within minutes of a release and trades *before* the market adjusts is trading information, not disagreement. This is testable with the same replay harness (compare price moves in the hour after releases).
5. **Station-true forecasting** — forecast the resolution station itself (METAR history + MOS-style correction per station), not a city grid point. Would fix the NYC-grade failures.
6. **Sell longshots instead of buying them** — the data says tails are *over*priced by naive buyers like us; the profitable side of our 7%-win-rate longshot buys was the seller's. Market-making/limit-order strategies are a different (harder) infrastructure problem, but the flow is on that side.

**Bottom line:** refine, don't fund. The weather models are fine; the *trading logic* buys exactly what an informed market is happiest to sell.

---

## 8. Reproduction

```bash
python3 backtest/fetch_weather.py london nyc seoul     # forecast + actuals archive
python3 backtest/fetch_polymarket.py london 2026-02-01 2026-07-06   # (× city)
python3 backtest/run_backtest.py                        # results.json + summary
python3 backtest/analyze_deep.py                        # breakdowns
```

Caveats: last-trade prices (not executable order-book quotes); no slippage; $10 flat stakes; ERA5 vs station truth in component A (component B uses the market's own resolution, avoiding this); 5 months of market data — young, thin markets that are visibly getting sharper month over month.
