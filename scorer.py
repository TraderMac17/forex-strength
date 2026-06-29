import pandas as pd

CURRENCIES = ["USD", "EUR", "GBP", "JPY", "AUD", "CAD", "NZD"]

PAIRS = [
    ("EUR", "USD"), ("GBP", "USD"), ("AUD", "USD"), ("NZD", "USD"),
    ("USD", "CAD"), ("USD", "JPY"),
    ("EUR", "GBP"), ("EUR", "AUD"), ("EUR", "NZD"), ("EUR", "CAD"), ("EUR", "JPY"),
    ("GBP", "AUD"), ("GBP", "NZD"), ("GBP", "CAD"), ("GBP", "JPY"),
    ("AUD", "NZD"), ("AUD", "CAD"), ("AUD", "JPY"),
    ("NZD", "CAD"), ("NZD", "JPY"),
    ("CAD", "JPY"),
]

PAIR_SYMBOLS = {f"{b}{q}": (b, q) for b, q in PAIRS}

TIMEFRAME_CANDLES = {
    "Daily": 20,
    "4H": 30,   # 5 days × 6 candles
    "1H": 48,   # 2 days × 24 candles
}


def score_candles(df: pd.DataFrame) -> int:
    """
    Score each candle vs previous using HH/HL = +1, LH/LL = -1, else 0.
    Returns the net sum over all candles.
    """
    highs = df["high"].values
    lows = df["low"].values
    total = 0
    for i in range(1, len(highs)):
        hh = highs[i] > highs[i - 1]
        hl = lows[i] > lows[i - 1]
        lh = highs[i] < highs[i - 1]
        ll = lows[i] < lows[i - 1]
        if hh and hl:
            total += 1
        elif lh and ll:
            total -= 1
        # inside bar or outside bar = neutral (0)
    return total


def classify_pair(score: int) -> int:
    """Return +1 (bullish), -1 (bearish), or 0 (neutral)."""
    if score > 0:
        return 1
    elif score < 0:
        return -1
    return 0


def compute_currency_scores(pair_scores: dict) -> dict:
    """
    pair_scores: { "EURUSD": int_score, ... }
    Returns { "USD": {"strong": int, "weak": int, "net": int}, ... }
    """
    results = {c: {"strong": 0, "weak": 0} for c in CURRENCIES}

    for symbol, raw_score in pair_scores.items():
        if symbol not in PAIR_SYMBOLS:
            continue
        base, quote = PAIR_SYMBOLS[symbol]
        direction = classify_pair(raw_score)

        if direction == 1:       # pair bullish → base strong, quote weak
            results[base]["strong"] += 1
            results[quote]["weak"] += 1
        elif direction == -1:    # pair bearish → base weak, quote strong
            results[base]["weak"] += 1
            results[quote]["strong"] += 1
        # neutral → no contribution

    for c in results:
        results[c]["net"] = results[c]["strong"] - results[c]["weak"]

    return results


def format_score(data: dict) -> str:
    """Format score as '+6', '-4/+2', '-6', or '0'."""
    s = data["strong"]
    w = data["weak"]
    net = data["net"]
    if w == 0 and s == 0:
        return "0"
    if w == 0:
        return f"+{s}"
    if s == 0:
        return f"-{w}"
    return f"-{w}/+{s}"


def strength_label(data: dict) -> str:
    net = data["net"]
    if net >= 4:
        return "STRONG"
    elif net <= -4:
        return "WEAK"
    return "NEUTRAL"
