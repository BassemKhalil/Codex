"""
Trading strategies for Polymarket weather contracts.

Two strategies:
  1. Consensus Edge — bet when our model-derived probability diverges from market price.
  2. High Confidence — bet only when models tightly agree and consensus is clearly one-sided.
"""

import math


def normal_cdf(x, mu=0.0, sigma=1.0):
    """Standard normal CDF using math.erf (exact, no scipy needed)."""
    if sigma <= 0:
        return 1.0 if x >= mu else 0.0
    return 0.5 * (1.0 + math.erf((x - mu) / (sigma * math.sqrt(2.0))))


def estimate_probability_over(threshold_c, median_c, std_c):
    """Estimate P(actual_high > threshold) assuming normal distribution."""
    if std_c <= 0:
        return 1.0 if median_c > threshold_c else 0.0
    return 1.0 - normal_cdf(threshold_c, mu=median_c, sigma=std_c)


def evaluate_consensus_edge(contract, consensus, strategy_cfg):
    """
    Consensus Edge strategy.
    Returns a trade signal dict or None if no trade.
    """
    if not strategy_cfg.get("enabled", True):
        return None

    threshold = contract["threshold_c"]
    market_yes = contract["market_yes_price"]
    median = consensus["median_high"]
    std = consensus["std_high"]

    if std > strategy_cfg.get("max_std_dev_c", 3.0):
        return None

    our_prob = estimate_probability_over(threshold, median, std)
    edge = our_prob - market_yes

    min_edge = strategy_cfg.get("min_edge", 0.15)

    if abs(edge) < min_edge:
        return None

    if edge > 0:
        side = "YES"
        entry_price = market_yes
    else:
        side = "NO"
        entry_price = 1.0 - market_yes
        edge = abs(edge)

    return {
        "strategy": "consensus_edge",
        "side": side,
        "entry_price": entry_price,
        "our_probability": our_prob,
        "market_probability": market_yes,
        "edge": edge,
        "model_median": median,
        "model_std": std,
    }


def evaluate_high_confidence(contract, consensus, strategy_cfg):
    """
    High Confidence strategy.
    Only trades when models tightly agree and probability is clearly one-sided.
    Returns a trade signal dict or None.
    """
    if not strategy_cfg.get("enabled", True):
        return None

    threshold = contract["threshold_c"]
    market_yes = contract["market_yes_price"]
    median = consensus["median_high"]
    std = consensus["std_high"]

    if std > strategy_cfg.get("max_std_dev_c", 1.0):
        return None

    our_prob = estimate_probability_over(threshold, median, std)
    min_prob = strategy_cfg.get("min_probability", 0.75)

    if our_prob >= min_prob:
        side = "YES"
        entry_price = market_yes
        edge = our_prob - market_yes
    elif (1.0 - our_prob) >= min_prob:
        side = "NO"
        entry_price = 1.0 - market_yes
        edge = (1.0 - our_prob) - (1.0 - market_yes)
    else:
        return None

    if edge <= 0:
        return None

    return {
        "strategy": "high_confidence",
        "side": side,
        "entry_price": entry_price,
        "our_probability": our_prob,
        "market_probability": market_yes,
        "edge": edge,
        "model_median": median,
        "model_std": std,
    }


def generate_signals(contract, consensus, strategy_config):
    """Run all enabled strategies and return list of trade signals."""
    signals = []

    sig = evaluate_consensus_edge(
        contract, consensus, strategy_config.get("consensus_edge", {})
    )
    if sig:
        signals.append(sig)

    sig = evaluate_high_confidence(
        contract, consensus, strategy_config.get("high_confidence", {})
    )
    if sig:
        signals.append(sig)

    return signals
