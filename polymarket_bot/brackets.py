"""
Parsing of Polymarket temperature bracket events.

Handles single-degree brackets ("18°C"), range brackets ("34-35°F"),
negative temperatures ("-2°C"), and edge brackets ("14°C or below",
"24°C or higher").
"""

import json
import re


def extract_temp_range(question):
    """
    -> (low, high, unit) or (None, None, None).
    "34-35°F" -> (34, 35, 'F');  "18°C" -> (18, 18, 'C');  "-2°C" -> (-2, -2, 'C')
    """
    m = re.search(r"(-?\d+)\s*[-–—]\s*(-?\d+)\s*°?\s*([CF])\b", question)
    if m:
        lo, hi = sorted([int(m.group(1)), int(m.group(2))])
        return lo, hi, m.group(3)
    m = re.search(r"(-?\d+)\s*°?\s*([CF])\b", question)
    if m:
        t = int(m.group(1))
        return t, t, m.group(2)
    m = re.search(r"be\s+(-?\d+)", question)
    if m:
        t = int(m.group(1))
        return t, t, None
    return None, None, None


def parse_bracket_event(event_data):
    """
    -> (brackets, unit). Each bracket:
       {temp (upper), temp_low, is_lower, is_upper, final (gamma yes price),
        yes_token_id, question}
    sorted by temp ascending.
    """
    brackets = []
    unit = "C"
    for mkt in event_data.get("markets", []):
        q = mkt.get("question", "")
        lo, hi, u = extract_temp_range(q)
        if lo is None:
            continue
        if u:
            unit = u

        ql = q.lower()
        is_lower = "or below" in ql or "or less" in ql
        is_upper = "or higher" in ql or "or above" in ql or "or more" in ql

        final = None
        prices = mkt.get("outcomePrices")
        if prices:
            if isinstance(prices, str):
                prices = json.loads(prices)
            if len(prices) >= 1:
                final = float(prices[0])

        token = None
        tokens = mkt.get("clobTokenIds")
        if tokens:
            if isinstance(tokens, str):
                tokens = json.loads(tokens)
            if tokens:
                token = tokens[0]

        brackets.append({
            "temp": hi, "temp_low": lo,
            "is_lower": is_lower, "is_upper": is_upper,
            "final": final, "yes_token_id": token, "question": q,
        })

    brackets.sort(key=lambda b: b["temp"])
    return brackets, unit


def find_bracket_for(brackets, value):
    """The non-edge bracket whose [temp_low, temp] range contains value."""
    for b in brackets:
        if b["is_lower"] or b["is_upper"]:
            continue
        if b["temp_low"] <= value <= b["temp"]:
            return b
    return None
