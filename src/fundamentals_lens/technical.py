"""
Pure-Python Technical Analysis MVP Engine for Fundamentals Lens.
Zero external heavy TA dependencies: built purely with standard library, pandas, numpy, and plotly.

Capabilities:
1. Strict in-memory OHLCV validation with structured diagnostic reports and full OHLC range invariant enforcement.
2. Core indicators: SMA(20/50/200), RSI(14) with Wilder's smoothing and flat-series handling, MACD(12,26,9), Bollinger Bands(20,2), ATR(14).
3. Performance & Risk: 1M/3M/6M/1Y returns, 52W High/Low coverage checks, annualized volatility, Max Drawdown.
4. Benchmark alignment: Exact common-date inner join, duration-guarded returns (never labeling < 252 bars as 1Y).
5. Interactive Plotly charts & exportable technical summary tables with prominent simulated demo badges.
"""

import math
from typing import Optional, Tuple, Dict, Any, List
import pandas as pd
import numpy as np

try:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    PLOTLY_AVAILABLE = True
except ImportError:
    PLOTLY_AVAILABLE = False

from .models import TechnicalSummary, OHLCVValidationReport, PriceAdjustmentBasis


def get_ohlcv_csv_template() -> str:
    """Returns a sample downloadable CSV template string with clear illustrative annotations."""
    return (
        "# Fundamentals Lens — OHLCV Data Template\n"
        "# Required Headers: Date, Open, High, Low, Close, Volume\n"
        "# Format: ISO 8601 YYYY-MM-DD for Date; numbers > 0 for prices; Volume >= 0\n"
        "# Invariants: High >= max(Open, Close, Low) and Low <= min(Open, Close, High)\n"
        "# Sample rows below are illustrative only:\n"
        "Date,Open,High,Low,Close,Volume\n"
        "2026-10-12,228.50,231.20,227.80,230.10,48200000\n"
        "2026-10-13,230.00,232.40,229.10,231.85,51400000\n"
        "2026-10-14,232.00,233.10,229.90,230.70,44300000\n"
        "2026-10-15,230.50,234.00,230.10,233.60,59100000\n"
        "2026-10-16,233.80,235.50,232.20,234.90,62000000\n"
    )


def validate_ohlcv_dataframe_with_report(
    df: pd.DataFrame, 
    allow_drop_duplicates: bool = False,
    ticker: Optional[str] = None,
    price_adjustment_basis: Any = PriceAdjustmentBasis.UNKNOWN,
    **kwargs
) -> Tuple[bool, Optional[str], Optional[pd.DataFrame], OHLCVValidationReport]:
    """
    Validates and standardizes an OHLCV dataframe.
    Enforces:
    - Required headers: Date, Open, High, Low, Close, Volume
    - ISO 8601 date parseability
    - Finite numeric checks (no NaN, Inf, non-numeric strings)
    - Positive prices: Open > 0, High > 0, Low > 0, Close > 0
    - Non-negative volume: Volume >= 0
    - Full range invariants: High >= max(Open, Close, Low) and Low <= min(Open, Close, High)
    - Duplicate dates & contradictory duplicate rows detection
    - Chronological sorting
    - Minimum history length (>= 20 trading bars)
    
    Returns: (is_valid, error_message, sanitized_dataframe, validation_report)
    """
    if isinstance(price_adjustment_basis, PriceAdjustmentBasis):
        basis_enum = price_adjustment_basis
    elif isinstance(price_adjustment_basis, str):
        try:
            basis_enum = PriceAdjustmentBasis(price_adjustment_basis)
        except Exception:
            basis_enum = PriceAdjustmentBasis.UNKNOWN
    else:
        basis_enum = PriceAdjustmentBasis.UNKNOWN

    errors: List[str] = []
    warnings: List[str] = []
    sample_offending: List[Dict[str, Any]] = []
    dup_dates: List[str] = []
    non_finite_dates: List[str] = []
    inv_dates: List[str] = []

    if df is None or df.empty:
        report = OHLCVValidationReport(
            is_valid=False,
            total_rows=0,
            valid_rows=0,
            error_count=1,
            warning_count=0,
            errors=["Uploaded file contains no data or could not be parsed."],
            ticker=ticker,
            price_adjustment_basis=basis_enum
        )
        return False, "Uploaded file contains no data or could not be parsed.", None, report

    total_rows = len(df)

    # 1. Header Resolution
    col_map = {str(c).strip().lower(): c for c in df.columns}
    required = ["date", "open", "high", "low", "close", "volume"]
    missing = [req for req in required if req not in col_map]

    if missing:
        err = f"Missing required headers: {', '.join(m.capitalize() for m in missing)}. Required headers: Date, Open, High, Low, Close, Volume."
        errors.append(err)
        report = OHLCVValidationReport(
            is_valid=False,
            total_rows=total_rows,
            valid_rows=0,
            error_count=len(errors),
            warning_count=0,
            errors=errors
        )
        return False, err, None, report

    clean_df = pd.DataFrame()

    # 2. Strict ISO 8601 Date validation & parsing
    raw_date_series = df[col_map["date"]]
    import re
    import datetime
    iso_date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    non_iso_samples = []
    for idx, val in raw_date_series.items():
        if pd.isna(val):
            continue
        if isinstance(val, (pd.Timestamp, np.datetime64, datetime.date, datetime.datetime)):
            continue
        val_str = str(val).strip()
        if not iso_date_pattern.match(val_str):
            non_iso_samples.append((idx, val_str))

    if non_iso_samples:
        errors.append(
            f"{len(non_iso_samples)} row(s) contain dates that do not strictly conform to ISO 8601 YYYY-MM-DD "
            f"(samples: {[s[1] for s in non_iso_samples[:3]]}). Format must conform strictly to YYYY-MM-DD."
        )
        for idx, s_val in non_iso_samples[:3]:
            sample_offending.append({"row_index": int(idx), "error": "Non-ISO 8601 date format", "raw_data": str(df.iloc[idx].to_dict())})

    clean_df["Date"] = pd.to_datetime(raw_date_series, errors="coerce")
    bad_date_mask = clean_df["Date"].isna()
    if bad_date_mask.any() and not non_iso_samples:
        bad_count = int(bad_date_mask.sum())
        sample_bad = df.loc[bad_date_mask, col_map["date"]].head(3).tolist()
        errors.append(f"{bad_count} row(s) contain unparseable dates (samples: {sample_bad}). Format must conform to YYYY-MM-DD.")
        for idx in df.loc[bad_date_mask].head(3).index:
            sample_offending.append({"row_index": int(idx), "error": "Unparseable date", "raw_data": str(df.iloc[idx].to_dict())})

    # 3. Numeric conversions & finite check
    for col in ["open", "high", "low", "close", "volume"]:
        clean_df[col.capitalize()] = pd.to_numeric(df[col_map[col]], errors="coerce")

    # Check for NaN / Inf
    numeric_cols = ["Open", "High", "Low", "Close", "Volume"]
    non_finite_mask = clean_df[numeric_cols].isna().any(axis=1) | np.isinf(clean_df[numeric_cols]).any(axis=1)
    if non_finite_mask.any():
        nf_count = int(non_finite_mask.sum())
        errors.append(f"{nf_count} row(s) contain missing (NaN) or infinite values in price/volume columns.")
        for idx in clean_df.loc[non_finite_mask].head(3).index:
            sample_offending.append({"row_index": int(idx), "error": "Non-finite price or volume", "raw_data": str(df.iloc[idx].to_dict())})
            if pd.notna(clean_df.loc[idx, "Date"]):
                non_finite_dates.append(str(clean_df.loc[idx, "Date"].strftime("%Y-%m-%d")))

    # 4. Positivity checks
    price_cols = ["Open", "High", "Low", "Close"]
    non_positive_mask = (clean_df[price_cols] <= 0).any(axis=1)
    if non_positive_mask.any():
        np_count = int(non_positive_mask.sum())
        errors.append(f"{np_count} row(s) have non-positive price values (<= 0). Prices must be strictly positive.")
        for idx in clean_df.loc[non_positive_mask].head(3).index:
            sample_offending.append({"row_index": int(idx), "error": "Non-positive price", "raw_data": str(df.iloc[idx].to_dict())})

    neg_volume_mask = clean_df["Volume"] < 0
    if neg_volume_mask.any():
        nv_count = int(neg_volume_mask.sum())
        errors.append(f"{nv_count} row(s) have negative volume (< 0). Volume must be non-negative.")

    # 5. Full OHLC Range Invariants
    # High >= max(Open, Close, Low)
    # Low <= min(Open, Close, High)
    high_invalid = (clean_df["High"] < clean_df["Open"]) | (clean_df["High"] < clean_df["Close"]) | (clean_df["High"] < clean_df["Low"])
    low_invalid = (clean_df["Low"] > clean_df["Open"]) | (clean_df["Low"] > clean_df["Close"]) | (clean_df["Low"] > clean_df["High"])
    range_invalid_mask = high_invalid | low_invalid

    if range_invalid_mask.any():
        ri_count = int(range_invalid_mask.sum())
        for idx in clean_df.loc[range_invalid_mask].head(3).index:
            r_date = clean_df.loc[idx, "Date"].strftime("%Y-%m-%d") if pd.notna(clean_df.loc[idx, "Date"]) else f"row {idx}"
            inv_dates.append(str(r_date))
            sample_offending.append({
                "row_index": int(idx),
                "error": "Range invariant violation (High must be >= Open/Close/Low, Low must be <= Open/Close/High)",
                "raw_data": str(df.iloc[idx].to_dict())
            })
        errors.append(f"Price invariant violation detected on {ri_count} row(s) (samples: {inv_dates[:3]}). High must be >= max(Open, Close, Low) and Low <= min(Open, Close, High).")

    # 6. Duplicate Dates Check
    if not bad_date_mask.all():
        valid_dates_series = clean_df.loc[~bad_date_mask, "Date"]
        duplicated_date_mask = valid_dates_series.duplicated(keep=False)
        if duplicated_date_mask.any():
            dup_dates = [d.strftime("%Y-%m-%d") for d in valid_dates_series[duplicated_date_mask].unique()[:5]]
            # Check if duplicates are contradictory
            dup_indices = valid_dates_series[duplicated_date_mask].index
            dup_subset = clean_df.loc[dup_indices]
            is_contradictory = False
            for d_val, grp in dup_subset.groupby("Date"):
                if grp[numeric_cols].nunique().max() > 1:
                    is_contradictory = True
                    break

            if is_contradictory:
                errors.append(f"Contradictory duplicate date entries detected for dates: {dup_dates}. Multiple rows with identical dates report differing prices.")
            elif not allow_drop_duplicates:
                errors.append(f"Duplicate date entries detected on dates: {dup_dates}. To resolve, remove duplicates in source or explicitly select deduplication mode.")
            else:
                warnings.append(f"Duplicate dates detected on dates: {dup_dates}; automatically retained first occurrence per explicit request.")

    # If critical errors exist, reject
    if errors:
        report = OHLCVValidationReport(
            is_valid=False,
            total_rows=total_rows,
            valid_rows=0,
            error_count=len(errors),
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            sample_offending_rows=sample_offending[:5],
            duplicate_dates=dup_dates,
            non_finite_dates=non_finite_dates,
            invariant_violation_dates=inv_dates,
            ticker=ticker,
            price_adjustment_basis=basis_enum
        )
        return False, errors[0], None, report

    # 7. Sorting & Final deduplication
    clean_df = clean_df.sort_values("Date")
    if clean_df["Date"].duplicated().any():
        clean_df = clean_df.drop_duplicates(subset=["Date"]).reset_index(drop=True)
    else:
        clean_df = clean_df.reset_index(drop=True)

    # 8. History length check
    valid_count = len(clean_df)
    if valid_count < 20:
        err = f"Insufficient trading observations ({valid_count} bars found). Technical analysis requires at least 20 trading periods."
        errors.append(err)
        report = OHLCVValidationReport(
            is_valid=False,
            total_rows=total_rows,
            valid_rows=valid_count,
            error_count=1,
            warning_count=len(warnings),
            errors=errors,
            warnings=warnings,
            ticker=ticker,
            price_adjustment_basis=basis_enum
        )
        return False, err, None, report

    clean_df["Date_Str"] = clean_df["Date"].dt.strftime("%Y-%m-%d")

    invariants = [
        "Required headers present (Date, Open, High, Low, Close, Volume)",
        "Strict ISO 8601 Date parseability",
        "Finite positive price values (Open, High, Low, Close > 0)",
        "Non-negative volume invariant (Volume >= 0)",
        "OHLC bounding invariants: High >= max(Open, Close, Low) and Low <= min(Open, Close, High)",
        "Chronological sorting & duplicate date integrity",
        f"Minimum observation threshold satisfied ({valid_count} >= 20 bars)"
    ]
    start_d = clean_df["Date_Str"].iloc[0] if valid_count > 0 else None
    end_d = clean_df["Date_Str"].iloc[-1] if valid_count > 0 else None

    report = OHLCVValidationReport(
        is_valid=True,
        total_rows=total_rows,
        valid_rows=valid_count,
        error_count=0,
        warning_count=len(warnings),
        errors=errors,
        warnings=warnings,
        sample_offending_rows=[],
        duplicate_dates=dup_dates,
        non_finite_dates=non_finite_dates,
        invariant_violation_dates=inv_dates,
        ticker=ticker,
        price_adjustment_basis=basis_enum,
        start_date=start_d,
        end_date=end_d,
        invariants_checked=invariants
    )
    return True, None, clean_df, report


def validate_ohlcv_dataframe(
    df: pd.DataFrame, 
    allow_drop_duplicates: bool = False,
    ticker: Optional[str] = None,
    price_adjustment_basis: Any = PriceAdjustmentBasis.UNKNOWN,
    **kwargs
) -> Tuple[bool, Optional[str], Optional[pd.DataFrame], OHLCVValidationReport]:
    """
    Validates an OHLCV dataframe.
    Returns: (is_valid, error_msg, sanitized_df, report).
    """
    return validate_ohlcv_dataframe_with_report(
        df,
        allow_drop_duplicates=allow_drop_duplicates,
        ticker=ticker,
        price_adjustment_basis=price_adjustment_basis,
        **kwargs
    )



def calculate_sma(series: pd.Series, period: int) -> pd.Series:
    """Calculates Simple Moving Average."""
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates Relative Strength Index using Wilder's smoothed moving average.
    Corner cases:
    - If series is completely flat (all price changes == 0): returns 50.0 (neutral).
    - If all changes are non-negative and sum > 0 (no loss): returns 100.0.
    - If all changes are non-positive and sum < 0 (no gain): returns 0.0.
    """
    if len(series) < 2:
        return pd.Series([np.nan] * len(series), index=series.index)

    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = (-delta).clip(lower=0.0)

    # Wilder's smoothing uses alpha = 1 / period
    avg_gain = gain.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()

    # Safe division
    denom = avg_loss.replace(0, np.nan)
    rs = avg_gain / denom
    rsi = 100.0 - (100.0 / (1.0 + rs))

    # Corner cases
    # 1. No loss but positive gain -> 100.0
    rsi = rsi.where(~((avg_loss == 0) & (avg_gain > 0)), 100.0)
    # 2. No gain but positive loss -> 0.0
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss > 0)), 0.0)
    # 3. Completely flat series (both avg_gain == 0 and avg_loss == 0) -> 50.0
    rsi = rsi.where(~((avg_gain == 0) & (avg_loss == 0)), 50.0)

    return rsi.round(2)


def calculate_macd(
    series: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD Line, Signal Line, and MACD Histogram."""
    fast_ema = calculate_ema(series, fast)
    slow_ema = calculate_ema(series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    macd_hist = macd_line - signal_line
    return macd_line.round(2), signal_line.round(2), macd_hist.round(2)


def calculate_bollinger_bands(
    series: pd.Series, 
    period: int = 20, 
    num_std: float = 2.0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates Bollinger Bands (Upper, Middle, Lower) using sample standard deviation (ddof=1)."""
    middle = calculate_sma(series, period)
    std = series.rolling(window=period, min_periods=period).std(ddof=1)
    upper = middle + (std * num_std)
    lower = middle - (std * num_std)
    return upper.round(2), middle.round(2), lower.round(2)


def calculate_atr(
    high: pd.Series, 
    low: pd.Series, 
    close: pd.Series, 
    period: int = 14
) -> pd.Series:
    """
    Calculates Average True Range using classic Wilder's smoothing:
    TR0 = High0 - Low0
    TRt = max(High - Low, abs(High - Close_prev), abs(Low - Close_prev))
    First valid ATR at index (period-1) is the SMA of TR over first period bars.
    Subsequent ATR values smoothed by Wilder's recurrence.
    """
    prior_close = close.shift(1)
    tr1 = high - low
    tr2 = (high - prior_close).abs()
    tr3 = (low - prior_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Initial period-bar SMA, then Wilder's exponential smoothing
    atr = tr.ewm(alpha=1.0 / period, min_periods=period, adjust=False).mean()
    return atr.round(2)


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Computes all technical indicators and appends them to dataframe."""
    out = df.copy()
    close = out["Close"]
    high = out["High"]
    low = out["Low"]

    # Moving Averages
    out["SMA_20"] = calculate_sma(close, 20).round(2)
    out["SMA_50"] = calculate_sma(close, 50).round(2)
    out["SMA_200"] = calculate_sma(close, 200).round(2)

    # Momentum & Trend
    out["RSI_14"] = calculate_rsi(close, 14)
    macd, signal, hist = calculate_macd(close, 12, 26, 9)
    out["MACD"] = macd
    out["MACD_Signal"] = signal
    out["MACD_Hist"] = hist

    # Volatility Bands & ATR
    upper, mid, lower = calculate_bollinger_bands(close, 20, 2.0)
    out["BB_Upper"] = upper
    out["BB_Middle"] = mid
    out["BB_Lower"] = lower
    out["ATR_14"] = calculate_atr(high, low, close, 14)

    # Returns
    out["Daily_Return"] = close.pct_change().round(4)
    return out


def compute_technical_summary(
    df: pd.DataFrame, 
    ticker: str = "ASSET",
    benchmark_df: Optional[pd.DataFrame] = None,
    benchmark_ticker: Optional[str] = None,
    is_simulated_demo: bool = False,
    price_adjustment_basis: str = "UNKNOWN",
    currency: str = "USD"
) -> TechnicalSummary:
    """
    Computes high-level technical summary cards, momentum states, and risk statistics.
    Guards:
    - 1-Year Return is only populated if >= 252 trading bars are available.
    - 52-Week High/Low is flagged as full 52-week only if >= 252 bars are available.
    - Benchmark return is only populated as 1-year if common overlapping history is >= 252 bars.
    """
    if "RSI_14" not in df.columns:
        df = compute_technical_indicators(df)

    n = len(df)
    last_row = df.iloc[-1]
    last_close = float(last_row["Close"])
    last_date = str(last_row["Date_Str"])

    # Multi-period returns
    def get_pct_change(lookback: int) -> Optional[float]:
        if n > lookback:
            prior_close = float(df.iloc[-1 - lookback]["Close"])
            if prior_close > 0:
                return round(((last_close / prior_close) - 1.0) * 100.0, 2)
        return None

    ret_1m = get_pct_change(21)
    ret_3m = get_pct_change(63)
    ret_6m = get_pct_change(126)
    # Strictly enforce 252 bars for 1Y
    ret_1y = get_pct_change(252)

    # 52-Week High & Low
    is_full_52w = (n >= 252)
    w_bars = df.tail(min(252, n))
    high_52w = float(w_bars["High"].max())
    low_52w = float(w_bars["Low"].min())
    dist_high = round(((last_close / high_52w) - 1.0) * 100.0, 2) if high_52w > 0 else None
    dist_low = round(((last_close / low_52w) - 1.0) * 100.0, 2) if low_52w > 0 else None

    # Annualized Volatility
    daily_returns = df["Close"].pct_change().dropna()
    if len(daily_returns) >= 10:
        ann_vol = round(float(daily_returns.std() * math.sqrt(252) * 100.0), 2)
    else:
        ann_vol = None

    # Maximum Drawdown
    cum_max = df["Close"].cummax()
    drawdowns = (df["Close"] - cum_max) / cum_max
    max_dd = round(float(drawdowns.min() * 100.0), 2) if len(drawdowns) > 0 else None

    # Current RSI Status
    curr_rsi = float(last_row["RSI_14"]) if pd.notna(last_row["RSI_14"]) else None
    if curr_rsi is not None:
        if curr_rsi >= 70.0:
            rsi_status = f"OVERBOUGHT ({curr_rsi:.1f} >= 70)"
        elif curr_rsi <= 30.0:
            rsi_status = f"OVERSOLD ({curr_rsi:.1f} <= 30)"
        else:
            rsi_status = f"NEUTRAL ({curr_rsi:.1f})"
    else:
        rsi_status = "N/A"

    # SMA Statuses
    def sma_stat(col: str) -> str:
        if pd.notna(last_row[col]):
            val = float(last_row[col])
            diff = ((last_close / val) - 1.0) * 100.0
            pos = "ABOVE" if diff >= 0 else "BELOW"
            return f"{pos} ({abs(diff):.1f}%)"
        return "N/A (< 200 bars)" if col == "SMA_200" and n < 200 else "N/A"

    sma_20_stat = sma_stat("SMA_20")
    sma_50_stat = sma_stat("SMA_50")
    sma_200_stat = sma_stat("SMA_200")

    # Benchmark comparison
    bm_1y = None
    rel_perf_1y = None
    bm_period_ret = None
    rel_perf_period = None
    common_bars = None
    common_start = None
    common_end = None

    if benchmark_df is not None and not benchmark_df.empty:
        # Align strictly on common dates
        merged = pd.merge(
            df[["Date", "Date_Str", "Close"]].rename(columns={"Close": "Asset_Close"}),
            benchmark_df[["Date", "Close"]].rename(columns={"Close": "Bench_Close"}),
            on="Date",
            how="inner"
        ).sort_values("Date")

        common_bars = len(merged)
        if common_bars >= 20:
            common_start = str(merged.iloc[0]["Date_Str"])
            common_end = str(merged.iloc[-1]["Date_Str"])
            first_b = float(merged.iloc[0]["Bench_Close"])
            last_b = float(merged.iloc[-1]["Bench_Close"])
            first_a = float(merged.iloc[0]["Asset_Close"])
            last_a = float(merged.iloc[-1]["Asset_Close"])

            if first_b > 0 and first_a > 0:
                bm_period_ret = round(((last_b / first_b) - 1.0) * 100.0, 2)
                asset_period_ret = round(((last_a / first_a) - 1.0) * 100.0, 2)
                rel_perf_period = round(asset_period_ret - bm_period_ret, 2)

                # Only assign 1-year benchmark change if common overlapping bars >= 252
                if common_bars >= 252:
                    bm_1y = bm_period_ret
                    rel_perf_1y = rel_perf_period

    return TechnicalSummary(
        ticker=ticker,
        last_date=last_date,
        last_close=last_close,
        total_bars=n,
        change_1m=ret_1m,
        change_3m=ret_3m,
        change_6m=ret_6m,
        change_1y=ret_1y,
        high_52w=high_52w,
        low_52w=low_52w,
        dist_from_52w_high=dist_high,
        dist_from_52w_low=dist_low,
        annualized_volatility=ann_vol,
        max_drawdown=max_dd,
        current_rsi=curr_rsi,
        rsi_status=rsi_status,
        sma_20_status=sma_20_stat,
        sma_50_status=sma_50_stat,
        sma_200_status=sma_200_stat,
        benchmark_ticker=benchmark_ticker,
        benchmark_change_1y=bm_1y,
        relative_performance_1y=rel_perf_1y,
        is_simulated_demo=is_simulated_demo,
        is_full_52w=is_full_52w,
        common_benchmark_bars=common_bars,
        common_benchmark_start=common_start,
        common_benchmark_end=common_end,
        benchmark_period_return=bm_period_ret,
        relative_performance_period=rel_perf_period,
        price_adjustment_basis=price_adjustment_basis,
        currency=currency
    )


def create_price_candlestick_chart(
    df: pd.DataFrame, 
    ticker: str = "ASSET",
    show_bb: bool = True,
    show_sma: bool = True,
    is_simulated_demo: bool = False
) -> Any:
    """Generates an interactive Plotly candlestick chart with SMA, Bollinger Bands, and Volume."""
    if not PLOTLY_AVAILABLE:
        return None

    badge = " [SIMULATED DEMO — NOT ACTUAL HISTORY]" if is_simulated_demo else ""

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
        subplot_titles=(f"{ticker}{badge} Daily Price Action & Overlays", "Trading Volume")
    )

    # Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df["Date"],
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            increasing_line_color="#00C805",
            decreasing_line_color="#FF3B30",
        ),
        row=1, col=1
    )

    # SMAs
    if show_sma:
        if "SMA_20" in df.columns and df["SMA_20"].notna().any():
            fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA_20"], name="SMA 20", line=dict(color="#FF9500", width=1.5)), row=1, col=1)
        if "SMA_50" in df.columns and df["SMA_50"].notna().any():
            fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA_50"], name="SMA 50", line=dict(color="#007AFF", width=1.5)), row=1, col=1)
        if "SMA_200" in df.columns and df["SMA_200"].notna().any():
            fig.add_trace(go.Scatter(x=df["Date"], y=df["SMA_200"], name="SMA 200", line=dict(color="#AF52DE", width=2.0, dash="dot")), row=1, col=1)

    # Bollinger Bands
    if show_bb and "BB_Upper" in df.columns and df["BB_Upper"].notna().any():
        fig.add_trace(go.Scatter(x=df["Date"], y=df["BB_Upper"], name="BB Upper (2.0σ)", line=dict(color="#8E8E93", width=1, dash="dash")), row=1, col=1)
        fig.add_trace(go.Scatter(x=df["Date"], y=df["BB_Lower"], name="BB Lower (2.0σ)", line=dict(color="#8E8E93", width=1, dash="dash"), fill="tonexty", fillcolor="rgba(142,142,147,0.08)"), row=1, col=1)

    # Volume Subplot
    colors = ["#00C805" if c >= o else "#FF3B30" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(
        go.Bar(x=df["Date"], y=df["Volume"], name="Volume", marker_color=colors, opacity=0.7),
        row=2, col=1
    )

    fig.update_layout(
        xaxis_rangeslider_visible=False,
        height=560,
        margin=dict(l=40, r=40, t=50, b=30),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig


def create_rsi_chart(df: pd.DataFrame, ticker: str = "ASSET", is_simulated_demo: bool = False) -> Any:
    """Generates an RSI(14) indicator chart with 70 and 30 threshold lines."""
    if not PLOTLY_AVAILABLE or "RSI_14" not in df.columns:
        return None

    badge = " [SIMULATED DEMO]" if is_simulated_demo else ""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df["Date"], y=df["RSI_14"], name="RSI (14)", line=dict(color="#5856D6", width=1.8)))

    # Overbought/Oversold thresholds
    fig.add_hline(y=70, line_dash="dash", line_color="#FF3B30", annotation_text="Overbought (70)", annotation_position="top left")
    fig.add_hline(y=30, line_dash="dash", line_color="#00C805", annotation_text="Oversold (30)", annotation_position="bottom left")
    fig.add_hline(y=50, line_dash="dot", line_color="#8E8E93", opacity=0.5)

    fig.update_layout(
        title=f"{ticker}{badge} 14-Day Relative Strength Index (RSI)",
        yaxis=dict(range=[0, 100], title="RSI Value"),
        xaxis=dict(title="Date"),
        height=280,
        margin=dict(l=40, r=40, t=50, b=30),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig


def create_macd_chart(df: pd.DataFrame, ticker: str = "ASSET", is_simulated_demo: bool = False) -> Any:
    """Generates MACD(12,26,9) line, Signal line, and Histogram chart."""
    if not PLOTLY_AVAILABLE or "MACD" not in df.columns:
        return None

    badge = " [SIMULATED DEMO]" if is_simulated_demo else ""
    fig = go.Figure()
    # Histogram
    hist_colors = ["#00C805" if h >= 0 else "#FF3B30" for h in df["MACD_Hist"]]
    fig.add_trace(go.Bar(x=df["Date"], y=df["MACD_Hist"], name="Histogram", marker_color=hist_colors, opacity=0.65))

    # MACD Line & Signal Line
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD"], name="MACD (12,26)", line=dict(color="#007AFF", width=1.8)))
    fig.add_trace(go.Scatter(x=df["Date"], y=df["MACD_Signal"], name="Signal (9)", line=dict(color="#FF9500", width=1.5, dash="dash")))

    fig.update_layout(
        title=f"{ticker}{badge} MACD Momentum Oscillator (12, 26, 9)",
        yaxis=dict(title="MACD"),
        xaxis=dict(title="Date"),
        height=280,
        margin=dict(l=40, r=40, t=50, b=30),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig


def create_benchmark_comparison_chart(
    df: pd.DataFrame, 
    benchmark_df: pd.DataFrame,
    asset_ticker: str = "Asset",
    benchmark_ticker: str = "Benchmark",
    is_simulated_demo: bool = False
) -> Any:
    """Generates normalized performance chart rebased to 100 on common start date."""
    if not PLOTLY_AVAILABLE or df is None or benchmark_df is None:
        return None

    merged = pd.merge(
        df[["Date", "Close"]].rename(columns={"Close": "Asset"}),
        benchmark_df[["Date", "Close"]].rename(columns={"Close": "Bench"}),
        on="Date",
        how="inner"
    ).sort_values("Date")

    if len(merged) < 5:
        return None

    merged["Asset_Norm"] = (merged["Asset"] / merged["Asset"].iloc[0]) * 100.0
    merged["Bench_Norm"] = (merged["Bench"] / merged["Bench"].iloc[0]) * 100.0

    badge = " [SIMULATED DEMO]" if is_simulated_demo else ""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged["Date"], y=merged["Asset_Norm"], name=asset_ticker, line=dict(color="#007AFF", width=2.2)))
    fig.add_trace(go.Scatter(x=merged["Date"], y=merged["Bench_Norm"], name=benchmark_ticker, line=dict(color="#8E8E93", width=1.8, dash="dash")))

    fig.update_layout(
        title=f"Relative Performance vs. {benchmark_ticker} (Base = 100){badge}",
        yaxis=dict(title="Normalized Performance (Base 100)"),
        xaxis=dict(title="Date"),
        height=340,
        margin=dict(l=40, r=40, t=50, b=30),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig
