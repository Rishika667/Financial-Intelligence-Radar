"""
Generates genuine, realistic 260-trading-day demo OHLCV datasets for Technical Analysis MVP:
- AAPL_daily_ohlcv.csv
- MSFT_daily_ohlcv.csv
- TCS_daily_ohlcv.csv
- SPY_benchmark_ohlcv.csv
"""

import math
import random
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
OHLCV_DIR = REPO_ROOT / "datasets" / "fundamentals_lens" / "ohlcv"
OHLCV_DIR.mkdir(parents=True, exist_ok=True)

# Generate 260 business days ending 2026-10-16
end_dt = date(2026, 10, 16)
curr_dt = end_dt
trading_days = []
while len(trading_days) < 260:
    if curr_dt.weekday() < 5:  # Monday to Friday
        trading_days.append(curr_dt)
    curr_dt -= timedelta(days=1)
trading_days.reverse()

# Deterministic seed for reproducible data
random.seed(42)
np.random.seed(42)

def generate_series(start_price, drift, vol, base_vol, price_round=2, vol_round=0):
    prices = [start_price]
    for _ in range(1, 260):
        # Geometric brownian motion step
        ret = np.random.normal(drift, vol)
        new_p = max(5.0, prices[-1] * (1.0 + ret))
        prices.append(new_p)
    
    rows = []
    for dt, close_p in zip(trading_days, prices):
        day_noise = np.random.uniform(-0.012, 0.012)
        open_p = close_p * (1.0 + day_noise)
        high_extra = abs(np.random.normal(0, 0.008))
        low_extra = abs(np.random.normal(0, 0.008))
        high_p = max(open_p, close_p) * (1.0 + high_extra)
        low_p = min(open_p, close_p) * (1.0 - low_extra)
        
        # Volume
        vol_noise = np.random.uniform(0.7, 1.4)
        vol_val = int(base_vol * vol_noise)
        
        rows.append({
            "Date": dt.strftime("%Y-%m-%d"),
            "Open": round(open_p, price_round),
            "High": round(high_p, price_round),
            "Low": round(low_p, price_round),
            "Close": round(close_p, price_round),
            "Volume": vol_val
        })
    return pd.DataFrame(rows)

# 1. AAPL
df_aapl = generate_series(start_price=188.50, drift=0.0008, vol=0.012, base_vol=52000000)
aapl_path = OHLCV_DIR / "AAPL_daily_ohlcv.csv"
df_aapl.to_csv(aapl_path, index=False)
print(f"Generated {aapl_path} ({len(df_aapl)} rows, close {df_aapl.iloc[0]['Close']} -> {df_aapl.iloc[-1]['Close']})")

# 2. MSFT
df_msft = generate_series(start_price=412.00, drift=0.0004, vol=0.011, base_vol=21000000)
msft_path = OHLCV_DIR / "MSFT_daily_ohlcv.csv"
df_msft.to_csv(msft_path, index=False)
print(f"Generated {msft_path} ({len(df_msft)} rows, close {df_msft.iloc[0]['Close']} -> {df_msft.iloc[-1]['Close']})")

# 3. TCS (INR)
df_tcs = generate_series(start_price=3750.00, drift=0.0005, vol=0.010, base_vol=2200000, price_round=2)
tcs_path = OHLCV_DIR / "TCS_daily_ohlcv.csv"
df_tcs.to_csv(tcs_path, index=False)
print(f"Generated {tcs_path} ({len(df_tcs)} rows, close {df_tcs.iloc[0]['Close']} -> {df_tcs.iloc[-1]['Close']})")

# 4. SPY Benchmark
df_spy = generate_series(start_price=512.50, drift=0.0006, vol=0.008, base_vol=61000000)
spy_path = OHLCV_DIR / "SPY_benchmark_ohlcv.csv"
df_spy.to_csv(spy_path, index=False)
print(f"Generated {spy_path} ({len(df_spy)} rows, close {df_spy.iloc[0]['Close']} -> {df_spy.iloc[-1]['Close']})")
