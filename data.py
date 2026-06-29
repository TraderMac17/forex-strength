import sys
sys.path.insert(0, '/Users/genesisinfinity/Library/Python/3.9/lib/python/site-packages')
import time
import pandas as pd
from tvDatafeed import TvDatafeed, Interval
from scorer import PAIR_SYMBOLS, TIMEFRAME_CANDLES, score_candles

TV_INTERVALS = {
    "Daily": Interval.in_daily,
    "4H":    Interval.in_4_hour,
    "1H":    Interval.in_1_hour,
}

BUFFER      = 10
RETRIES     = 3
DELAY       = 2
FULL_RETRY  = 3
FULL_DELAY  = 30


def get_tv():
    return TvDatafeed()


def fetch_pair(tv, symbol, interval, n_bars):
    for attempt in range(RETRIES):
        try:
            df = tv.get_hist(symbol=symbol, exchange="FX_IDC", interval=interval, n_bars=n_bars + BUFFER)
            if df is not None and len(df) >= 2:
                return df.tail(n_bars + 1).reset_index(drop=True)
        except Exception:
            pass
        if attempt < RETRIES - 1:
            time.sleep(DELAY)
    return None


def fetch_all_scores(progress_callback=None, status_callback=None):
    symbols = list(PAIR_SYMBOLS.keys())
    total   = len(symbols) * len(TIMEFRAME_CANDLES)

    for full_attempt in range(FULL_RETRY):
        tv      = get_tv()
        results = {tf: {} for tf in TIMEFRAME_CANDLES}
        failed  = []
        done    = 0

        for tf, n_candles in TIMEFRAME_CANDLES.items():
            interval = TV_INTERVALS[tf]
            for symbol in symbols:
                df = fetch_pair(tv, symbol, interval, n_candles)
                if df is not None:
                    results[tf][symbol] = score_candles(df)
                else:
                    results[tf][symbol] = 0
                    failed.append(f"{symbol} ({tf})")
                done += 1
                if progress_callback:
                    progress_callback(done / total, f"Fetching {symbol} {tf}...")

        if len(failed) < total / 2:
            return results, failed

        full_attempt_num = full_attempt + 1
        if full_attempt_num < FULL_RETRY:
            if status_callback:
                status_callback(f"Too many failures - retrying in {FULL_DELAY}s (attempt {full_attempt_num + 1}/{FULL_RETRY})...")
            time.sleep(FULL_DELAY)

    return results, failed