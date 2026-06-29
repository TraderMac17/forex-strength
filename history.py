import json
import os
import time

HISTORY_FILE = os.path.expanduser("~/forex-strength/score_history.json")
MAX_ENTRIES  = 48


def save_snapshot(currency_scores: dict):
    history = load_history()
    snapshot = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime()),
        "scores": {}
    }
    for tf, scores in currency_scores.items():
        snapshot["scores"][tf] = {
            cur: {
                "net":    scores[cur]["net"],
                "strong": scores[cur]["strong"],
                "weak":   scores[cur]["weak"],
            }
            for cur in scores
        }
    history.append(snapshot)
    if len(history) > MAX_ENTRIES:
        history = history[-MAX_ENTRIES:]
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []


def get_score_change(currency_scores: dict, tf: str, currency: str):
    history = load_history()
    if len(history) < 2:
        return None
    prev = history[-2]["scores"].get(tf, {}).get(currency)
    curr = currency_scores[tf][currency]
    if prev is None:
        return None
    return curr["net"] - prev["net"]
