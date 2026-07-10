# Model-Skill Backtest — Is the Forecast Signal Worth Betting On?

**Date:** 2026-07-09 · **Scope:** 5.5 years of as-issued forecasts (London 2021→2026; NYC/Seoul 2024→2026), leads 1–7 days, verified against observed outcomes; plus real-market anchors on all 5 months of Polymarket data.

**Answer: yes — the forecast signal is strong enough to build betting logic on. It prints money against any counterparty that doesn't have it, and it is fairly priced (not exploitable) against the counterparty that does. The edge therefore lives in *timing and venue selection*, not in a better thermometer.**

---

## ⚠️ Correction to the previous report

NYC bracket questions are **2°F ranges** ("34–35°F"); the harvester's regex read them as negative single values, inverting NYC's bracket ordering. All NYC rows in the previous strategy replay were structurally corrupted. Excluding NYC:

| | Previous (3 cities) | Corrected (London+Seoul only) |
|---|---|---|
| Live-config replay | −$402, −8.0% ROI | **+$31, +0.9% ROI** (345 trades, 36.8% win) |

The corrected conclusion is *"zero edge, coin-flip against the market"* rather than *"strongly negative."* The head-to-head skill gap stands unchanged: on chosen thresholds the market's Brier beats ours in both valid cities (London 0.18 vs 0.26; Seoul 0.17 vs 0.49). The strategic conclusions below supersede the previous report's.

---

## 1. Raw forecast skill, 2021 → 2026

Exact-bracket hit rate = how often the ensemble median lands in the *exact* 1° Polymarket bracket. This number **is** the fair price of the model's favorite bracket.

**London (full 6-model era, n≈880/lead):**

| Lead | MAE | Exact bracket | Within ±1 |
|---|---|---|---|
| 1 day | 0.56° | **49.8%** | 93.0% |
| 2 days | 0.69° | 45.5% | 88.6% |
| 3 days | 0.81° | 40.4% | 83.9% |
| 4 days | 1.03° | 37.7% | 75.4% |
| 5 days | 1.24° | 29.2% | 68.8% |

**2021–2024 (GFS+JMA only, n≈1,010/lead):** lead-1 hit 42.8% → the 6-model upgrade adds ~7 points. Skill has been stable across all five years (no regime luck).

**Cities are not equal:** lead-1 exact-bracket = London 50%, Seoul 37%, NYC 30% (NYC MAE is 2× London's — continental volatility + grid-vs-station gap). Any strategy calibrated on London will overpay everywhere else.

## 2. Against a naive counterparty: hugely profitable

Simulated bookmaker pricing brackets from 30-year climatology (the strongest "no-forecast" opponent), 2021→2026, betting only where model probability exceeds price by ≥15 points:

| Lead | Trades | Win rate | ROI |
|---|---|---|---|
| 1 day | 3,415 | 40% | **+442%** |
| 3 days | 3,421 | 33% | +355% |
| 5 days | 937 | 26% | +522% |

Adding a 5% vig barely dents it. Profitable **every single year, 2021 through 2026**. This is the cleanest possible answer to "is the signal real": a day-ahead NWP ensemble annihilates climatology-grade pricing at every lead tested. The logic itself is sound — *if* you can find a counterparty pricing anywhere near climatology.

## 3. Against the real Polymarket: fairly priced at expiry, soft at the open

Concrete strategy: buy the model's modal bracket, $10 flat, at real historical prices.

| Entry point | City | Trades | Hit rate | Avg price paid | ROI |
|---|---|---|---|---|---|
| Midnight before target (lead 1) | London | 145 | 35.2% | $0.385 | **−13.4%** |
| Midnight before target (lead 1) | Seoul | 64 | 31.2% | $0.245 | −0.0% |
| **Market open, 2–3 days out** | London | 131 | 30.5% | $0.291 | **+4.1%** |
| **Market open, 2–3 days out** | Seoul | 60 | 30.0% | $0.230 | **+20.6%** |

The pattern: by the night before, the market charges *more* than the model's true hit rate — it has already priced in everything the models know, plus station-specific and fresher information. But **at market open, 2–3 days out, prices sit below the models' realized hit rates** — positive ROI in both valid cities. Young books are still anchored near climatology (exactly the counterparty from §2 that the models beat).

Honest caveats: 191 open-trades total, thin young books, last-trade prices — suggestive, not proof. February 2026 (the softest month, newest markets) contributes disproportionately.

## 4. What this means for the bot

1. **Keep the model-consensus foundation.** The signal is real, stable across 5 years, and correctly probabilistic (calibration confirmed in the previous report). Nothing about the weather side needs replacing.
2. **Move the trading window from expiry-eve to market open.** All the exploitable mispricing this data can see lives in the first hours of a market's life, 2–3 days out — using the matching lead-2/3 forecast. Trading at midnight before the target day is trading *against* better information; trading at the open is trading *with* better information against climatology-anchored prices.
3. **Price ceilings from hit rates, per city and lead** — never pay above: London L1 $0.48 / L2 $0.44 / L3 $0.39; Seoul ~$0.35 L1; NYC ~$0.28 L1 (and fix range-bracket parsing before touching NYC at all).
4. **Drop the max-|edge| bracket picker** (adverse selection, previous report) in favor of: modal-bracket (and adjacent) value checks at market open against those ceilings.
5. **Next validation step before any real money:** paper-trade the open-window strategy live for 4–6 weeks (the bot infrastructure already supports this — it only needs the discovery loop to catch markets at creation, not at T-1), and require the live hit-rate-vs-price gap to persist outside February.

## 5. Reproduction

```bash
python3 backtest/fetch_leads.py london nyc seoul   # multi-lead archives + climatology
python3 backtest/model_skill.py                     # skill, climo-sim, market anchors
```

Truth source for §1–2 is ERA5 reanalysis (grid), for §3 the market's own resolution — the §3 numbers are therefore immune to the grid-vs-station gap; §1 hit rates may shift ±2–3 points against station data (the direction that matters for NYC).
