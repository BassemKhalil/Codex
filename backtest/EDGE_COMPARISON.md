# Edge Candidate Comparison — Release-Latency vs Station-True Forecasting

**Date:** 2026-07-20 · **Verdict: build Station-True (B). Reject Release-Latency (A).**

## The question

The open-window strategy is ~breakeven since May. Two proposed edges were on the
table; both were tested against data before building anything.

## Candidate A — model-release latency trading

*Thesis:* new model runs (GFS ~05/11/17/23 UTC, ECMWF ~07:30/19:30 UTC) shift
forecasts; trade the shift before the market reprices.

*Test:* hour-by-hour price appreciation of the eventual winning bracket across
all 164 resolved London markets, release windows vs other hours.

*Result — thesis rejected:*

- Release windows (05–09, 17–21 UTC ≈ 42% of hours) produce only **22%** of the
  winner's total price appreciation — *under*-weighted, not over-weighted.
- Price discovery peaks **13:00–17:00 UTC on the target day** — traders bidding
  the bracket as the actual afternoon high develops at the station in real time.
- The market's information engine is **same-day observations**, which cannot be
  front-run with day-ahead model data at any polling speed.
- Would also require minute-level polling + fast execution infrastructure for a
  thesis the data disfavors.

## Candidate B — station-true forecasting

*Discovery:* the markets resolve on Wunderground readings at **London City
Airport (EGLC, 51.505, 0.055)** — ~14 km east of the point the bot forecasts,
on the Thames estuary. Estuary cooling grows in heat — measured resolution-vs-
grid gap drifted from −0.5 °C (winter) to **+1.1 °C (mid-July)**. This is the
root cause of the July 0-for-13 wipeout.

*Test:* re-fetched all as-issued forecasts at EGLC coordinates (Feb–Jul 2026)
and re-ran the lead-2 modal comparison on every resolved market.

*Results:*

| Lead-2 modal hit rate | Feb | Mar | Apr | May | Jun | **Jul** | Total |
|---|---|---|---|---|---|---|---|
| Grid forecast (current bot) | 46% | 37% | 23% | 21% | 27% | 32% | 30% |
| **EGLC-point forecast** | 50% | 30% | 27% | 21% | 30% | **42%** | **32%** |
| Market favorite at open | 8% | 20% | 17% | 21% | 30% | 26% | 20% |

Replay (buy EGLC modal at lead-2 open, model-EV filter, $10 stakes):

| Config | n | Win | P&L | ROI | Feb–Apr | **May–Jul** |
|---|---|---|---|---|---|---|
| ceiling 0.455 + model-EV | 57 | 35% | +$180 | **+31.6%** | +$2 | **+$178** |
| no filter | 64 | 33% | +$136 | +21.3% | −$28 | +$164 |
| ceiling 0.40 + model-EV | 54 | 33% | +$163 | +30.2% | −$15 | +$178 |

Every configuration positive; profit concentrated in the **mature-market
months** — the opposite of the old grid strategy, whose profit was a young-
market artifact. The market favorite at the lead-2 open hits only 20%: the
market is *not* sharp at open (it sharpens on target-day observations), so a
better-aimed forecast retains an exploitable window.

## Caveats

n≈60 trades, one city, 5.5 months, last-trade prices. EGLC was identified
*after* diagnosing July, but the mechanism is causal, not curve-fit: the
contract text names the station; forecasting the resolution point is
correctness. Open-Meteo at EGLC coords is still grid interpolation — a
future MOS correction against actual EGLC METAR observations is the next
increment (July suggests meaningful headroom: 42% vs grid 32%).

## Recommended build

1. Point the bot's forecasts at the **resolution station coordinates** per city
   (parse the station from each market's description — it's in the contract).
2. Keep open-window timing (lead 2–3); add the **model-EV filter**
   (never pay above the model's own bracket probability) and **robust σ**.
3. Paper-trade 4–6 weeks; a losing-streak circuit breaker as a safety net.
4. Skip release-latency entirely.

Reproduce: `python3 backtest/compare_edges.py`
