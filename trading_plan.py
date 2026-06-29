from scorer import PAIRS, strength_label, format_score

CONFIDENCE = {
    ("STRONG", "WEAK"):     ("LONG",    "High"),
    ("STRONG", "NEUTRAL"):  ("LONG",    "Medium"),
    ("NEUTRAL", "WEAK"):    ("LONG",    "Low"),
    ("WEAK",   "STRONG"):   ("SHORT",   "High"),
    ("WEAK",   "NEUTRAL"):  ("SHORT",   "Medium"),
    ("NEUTRAL", "STRONG"):  ("SHORT",   "Low"),
    ("STRONG", "STRONG"):   ("NEUTRAL", None),
    ("WEAK",   "WEAK"):     ("NEUTRAL", None),
    ("NEUTRAL", "NEUTRAL"): ("NEUTRAL", None),
}


def find_correlated(trades):
    correlated = set()
    active = [t for t in trades if t["direction"] in ("LONG", "SHORT")]
    for i, t1 in enumerate(active):
        for t2 in active[i+1:]:
            if t1["direction"] != t2["direction"]:
                continue
            shared = set([t1["base"], t1["quote"]]) & set([t2["base"], t2["quote"]])
            if shared:
                if abs(t1["net_diff"]) >= abs(t2["net_diff"]):
                    correlated.add(t2["pair"])
                else:
                    correlated.add(t1["pair"])
    return correlated


def dominant_score(data):
    s = data["strong"]
    w = data["weak"]
    if w > 0 and s > 0:
        if w >= s:
            return "-" + str(w)
        else:
            return "+" + str(s)
    return format_score(data)


def generate_plan(currency_scores):
    trades = []

    for base, quote in PAIRS:
        symbol     = base + quote
        base_data  = currency_scores[base]
        quote_data = currency_scores[quote]

        base_label  = strength_label(base_data)
        quote_label = strength_label(quote_data)

        direction, confidence = CONFIDENCE.get((base_label, quote_label), ("NEUTRAL", None))

        net_diff = base_data["net"] - quote_data["net"]

        if direction in ("LONG", "SHORT") and abs(net_diff) < 5:
            direction  = "NEUTRAL"
            confidence = None

        trades.append({
            "pair":        symbol,
            "base":        base,
            "quote":       quote,
            "base_label":  base_label,
            "quote_label": quote_label,
            "direction":   direction,
            "confidence":  confidence,
            "base_net":    base_data["net"],
            "quote_net":   quote_data["net"],
            "base_score":  dominant_score(base_data),
            "quote_score": dominant_score(quote_data),
            "net_diff":    net_diff,
            "correlated":  False,
        })

    correlated_pairs = find_correlated(trades)
    for t in trades:
        if t["pair"] in correlated_pairs:
            t["correlated"] = True

    confidence_rank = {"High": 0, "Medium": 1, "Low": 2, None: 3}
    direction_rank  = {"LONG": 0, "SHORT": 1, "NEUTRAL": 2}

    trades.sort(key=lambda t: (
        direction_rank[t["direction"]],
        confidence_rank[t["confidence"]],
        -abs(t["net_diff"]),
    ))

    return trades


def best_trade(trades):
    for t in trades:
        if t["direction"] in ("LONG", "SHORT") and t["confidence"] == "High" and not t["correlated"]:
            return t
    for t in trades:
        if t["direction"] in ("LONG", "SHORT") and t["confidence"] == "Medium" and not t["correlated"]:
            return t
    return None