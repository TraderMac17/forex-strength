import sys
sys.path.insert(0, '/Users/genesisinfinity/Library/Python/3.9/lib/python/site-packages')
import time
import pandas as pd
import yfinance as yf
from scorer import PAIR_SYMBOLS, TIMEFRAME_CANDLES, score_candles

# Yahoo Finance symbol mapping
# Format: EURUSD -> EURUSD=X
YF_INTERVALS = {
    "Daily": ("1d", "3mo"),
    "4H":    ("1h", "7d"),
    "1H":    ("1h", "3d"),
}

TIMEFRAME_CANDLES_MAP = {
    "Daily": 20,
    "4H":    30,
    "1H":    48,
}


def get_yf_symbol(symbol):
    return symbol + "=X"


def fetch_pair(symbol, tf):
    yf_symbol = get_yf_symbol(symbol)
    interval, period = YF_INTERVALS[tf]
    try:
        df = yf.download(
            yf_symbol,
            interval=interval,
            period=period,
            progress=False,
            auto_adjust=True,
        )
        if df is None or len(df) < 2:
            return None
        df = df.rename(columns={
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume",
        })
        n = TIMEFRAME_CANDLES_MAP[tf]
        return df.tail(n + 1).reset_index(drop=True)
    except Exception as e:
        return None


def fetch_all_scores(progress_callback=None, status_callback=None):
    symbols = list(PAIR_SYMBOLS.keys())
    total   = len(symbols) * len(TIMEFRAME_CANDLES_MAP)
    results = {tf: {} for tf in TIMEFRAME_CANDLES_MAP}
    failed  = []
    done    = 0

    for tf in TIMEFRAME_CANDLES_MAP:
        for symbol in symbols:
            df = fetch_pair(symbol, tf)
            if df is not None and len(df) >= 2:
                results[tf][symbol] = score_candles(df)
            else:
                results[tf][symbol] = 0
                failed.append(symbol + " (" + tf + ")")
            done += 1
            if progress_callback:
                progress_callback(done / total, "Fetching " + symbol + " " + tf + "...")

    return results, failed