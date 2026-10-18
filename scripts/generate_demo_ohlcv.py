"""
Generates transparent, mathematically simulated demo OHLCV datasets for Technical Analysis:
- SIMULATED_TECH_EQUITY.csv (Simulated high-growth technology equity, 260 trading bars)
- SIMULATED_MARKET_BENCHMARK.csv (Simulated broad market index benchmark, 260 trading bars)

NON-NEGOTIABLE POLICY:
These files are strictly illustrative synthetic demonstrations generated via geometric Brownian motion.
They must NEVER be represented or labeled as real AAPL, MSFT, TCS, or SPY market history.
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

# Deterministic seed for reproducible simulation
random.seed(42)
np.random.seed(42)

def generate_series(start_price, drift, vol, base_vol, price_round=2):
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
        
        # Enforce invariant strictly: High >= max(Open, Close) and Low <= min(Open, Close)
        high_p = max(high_p, max(open_p, close_p))
        low_p = min(low_p, min(open_p, close_p))
        
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


def main():
    # 1. Clean up any legacy misleading ticker CSVs
    legacy_files = ["AAPL_daily_ohlcv.csv", "MSFT_daily_ohlcv.csv", "TCS_daily_ohlcv.csv", "SPY_benchmark_ohlcv.csv"]
    for lf in legacy_files:
        p = OHLCV_DIR / lf
        if p.exists():
            p.unlink()
            print(f"Removed legacy synthetic file: {lf}")

    # 2. Generate SIMULATED_TECH_EQUITY.csv
    df_equity = generate_series(start_price=188.50, drift=0.0007, vol=0.012, base_vol=45000000)
    equity_path = OHLCV_DIR / "SIMULATED_TECH_EQUITY.csv"
    df_equity.to_csv(equity_path, index=False)
    print(f"Generated {equity_path.name} ({len(df_equity)} bars, Close: {df_equity.iloc[0]['Close']} -> {df_equity.iloc[-1]['Close']})")

    # 3. Generate SIMULATED_MARKET_BENCHMARK.csv
    df_bench = generate_series(start_price=500.00, drift=0.0004, vol=0.007, base_vol=65000000)
    bench_path = OHLCV_DIR / "SIMULATED_MARKET_BENCHMARK.csv"
    df_bench.to_csv(bench_path, index=False)
    print(f"Generated {bench_path.name} ({len(df_bench)} bars, Close: {df_bench.iloc[0]['Close']} -> {df_bench.iloc[-1]['Close']})")


if __name__ == "__main__":
    main()
