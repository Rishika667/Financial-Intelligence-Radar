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

    # 1. Header Resolution & Ambiguity Check
    lower_cols = [str(c).strip().lower() for c in df.columns]
    dup_headers = [c for c in set(lower_cols) if lower_cols.count(c) > 1]
    if dup_headers:
        err = f"Ambiguous duplicate headers detected: {sorted(dup_headers)}. Each column header must appear uniquely."
        errors.append(err)
        report = OHLCVValidationReport(
            is_valid=False,
            total_rows=total_rows,
            valid_rows=0,
            error_count=len(errors),
            warning_count=0,
            errors=errors,
            ticker=ticker,
            price_adjustment_basis=basis_enum
        )
        return False, err, None, report

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
            errors=errors,
            ticker=ticker,
            price_adjustment_basis=basis_enum
        )
        return False, err, None, report

    clean_df = pd.DataFrame()

    # 2. Strict ISO 8601 Date validation & parsing
    raw_date_series = df[col_map["date"]]
    import re
    import datetime
    iso_date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    pos_map = {lbl: pos for pos, lbl in enumerate(df.index)}

    def _extract_sample_row(idx_lbl, err_desc: str):
        pos = pos_map.get(idx_lbl, 0)
        try:
            row_raw = df.loc[idx_lbl]
            row_dict = row_raw.iloc[0].to_dict() if isinstance(row_raw, pd.DataFrame) else row_raw.to_dict()
        except Exception:
            try:
                row_dict = df.iloc[pos].to_dict()
            except Exception:
                row_dict = {"index": str(idx_lbl)}
        row_idx_val = int(idx_lbl) if isinstance(idx_lbl, (int, np.integer)) else pos
        return {
            "row_index": row_idx_val,
            "position": pos,
            "error": err_desc,
            "raw_data": str(row_dict)
        }

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
            sample_offending.append(_extract_sample_row(idx, "Non-ISO 8601 date format"))

    clean_df["Date"] = pd.to_datetime(raw_date_series, errors="coerce")
    bad_date_mask = clean_df["Date"].isna()
    if bad_date_mask.any() and not non_iso_samples:
        bad_count = int(bad_date_mask.sum())
        sample_bad = df.loc[bad_date_mask, col_map["date"]].head(3).tolist()
        errors.append(f"{bad_count} row(s) contain unparseable dates (samples: {sample_bad}). Format must conform to YYYY-MM-DD.")
        for idx in df.loc[bad_date_mask].head(3).index:
            sample_offending.append(_extract_sample_row(idx, "Unparseable date"))

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
            sample_offending.append(_extract_sample_row(idx, "Non-finite price or volume"))
            if pd.notna(clean_df.loc[idx, "Date"]):
                non_finite_dates.append(str(clean_df.loc[idx, "Date"].strftime("%Y-%m-%d")))

    # 4. Positivity checks
    price_cols = ["Open", "High", "Low", "Close"]
    non_positive_mask = (clean_df[price_cols] <= 0).any(axis=1)
    if non_positive_mask.any():
        np_count = int(non_positive_mask.sum())
        errors.append(f"{np_count} row(s) have non-positive price values (<= 0). Prices must be strictly positive.")
        for idx in clean_df.loc[non_positive_mask].head(3).index:
            sample_offending.append(_extract_sample_row(idx, "Non-positive price"))

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
            sample_offending.append(_extract_sample_row(idx, "Range invariant violation (High must be >= Open/Close/Low, Low must be <= Open/Close/High)"))
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
    if not clean_df["Date"].is_monotonic_increasing:
        warnings.append("Input dates were not in ascending chronological order; normalized into ascending order.")
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
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive integer >= 1 (got {period} of type {type(period).__name__})")
    return series.rolling(window=period, min_periods=period).mean()


def calculate_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculates Exponential Moving Average."""
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive integer >= 1 (got {period} of type {type(period).__name__})")
    return series.ewm(span=period, adjust=False).mean()


def calculate_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """
    Calculates Relative Strength Index using Wilder's smoothed moving average:
    1. First (period) price changes (t = 1..period) are seeded with their simple moving average (SMA).
    2. First valid RSI is at index (period) corresponding to the (period+1)-th price observation.
    3. Subsequent periods smoothed with Wilder's recurrence:
       AvgGain_t = (AvgGain_{t-1} * (period - 1) + Gain_t) / period
       AvgLoss_t = (AvgLoss_{t-1} * (period - 1) + Loss_t) / period
    Corner cases:
    - Flat series (AvgGain == 0 and AvgLoss == 0): returns 50.0 (neutral).
    - Monotonically rising (AvgLoss == 0, AvgGain > 0): returns 100.0.
    - Monotonically falling (AvgGain == 0, AvgLoss > 0): returns 0.0.
    """
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive integer >= 1 (got {period} of type {type(period).__name__})")
    clean = pd.to_numeric(series, errors="coerce").values
    n = len(clean)
    if n < period + 1:
        return pd.Series([np.nan] * n, index=series.index)

    diff = np.diff(clean)
    gains = np.maximum(diff, 0.0)
    losses = np.maximum(-diff, 0.0)

    rsi = np.full(n, np.nan, dtype=np.float64)

    def _eval_rsi(ag: float, al: float) -> float:
        if al == 0.0 and ag == 0.0:
            return 50.0
        if al == 0.0:
            return 100.0
        if ag == 0.0:
            return 0.0
        rs = ag / al
        return 100.0 - (100.0 / (1.0 + rs))

    # Seed recurrence at index 'period' with the SMA of the first 'period' gains and losses
    avg_gain = float(np.mean(gains[:period]))
    avg_loss = float(np.mean(losses[:period]))
    rsi[period] = _eval_rsi(avg_gain, avg_loss)

    for i in range(period, len(diff)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rsi[i + 1] = _eval_rsi(avg_gain, avg_loss)

    return pd.Series(rsi, index=series.index).clip(lower=0.0, upper=100.0).round(2)


def calculate_macd(
    series: pd.Series, 
    fast: int = 12, 
    slow: int = 26, 
    signal: int = 9
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """Calculates MACD Line, Signal Line, and MACD Histogram."""
    for name, p in (("fast", fast), ("slow", slow), ("signal", signal)):
        if not isinstance(p, int) or isinstance(p, bool) or p <= 0:
            raise ValueError(f"MACD periods must be positive integers >= 1 (got {name}={p} of type {type(p).__name__})")
    if fast >= slow:
        raise ValueError(f"fast period must be strictly less than slow period (got fast={fast}, slow={slow})")
    clean_series = pd.to_numeric(series, errors="coerce")
    fast_ema = calculate_ema(clean_series, fast)
    slow_ema = calculate_ema(clean_series, slow)
    macd_line = fast_ema - slow_ema
    signal_line = calculate_ema(macd_line, signal)
    macd_hist = macd_line - signal_line
    return macd_line.round(2), signal_line.round(2), macd_hist.round(2)


def calculate_bollinger_bands(
    series: pd.Series, 
    period: int = 20, 
    num_std: float = 2.0,
    ddof: int = 0
) -> Tuple[pd.Series, pd.Series, pd.Series]:
    """
    Calculates Bollinger Bands (Upper, Middle, Lower).
    Uses population standard deviation (ddof=0) by default per John Bollinger's canonical definition:
    sigma = sqrt( (1 / N) * sum( (P_i - SMA)^2 ) ).
    Can optionally compute sample standard deviation with ddof=1.
    """
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive integer >= 1 (got {period} of type {type(period).__name__})")
    if not isinstance(num_std, (int, float)) or isinstance(num_std, bool) or num_std < 0:
        raise ValueError(f"num_std must be non-negative (got {num_std})")
    if ddof not in (0, 1) or isinstance(ddof, bool):
        raise ValueError(f"ddof must be 0 (population std) or 1 (sample std), got {ddof}")
    clean_series = pd.to_numeric(series, errors="coerce")
    middle = calculate_sma(clean_series, period)
    std = clean_series.rolling(window=period, min_periods=period).std(ddof=ddof)
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
    TRt = max(High_t - Low_t, abs(High_t - Close_{t-1}), abs(Low_t - Close_{t-1}))
    First valid ATR at index (period - 1) is the simple average (SMA) of TR over the first period bars.
    Subsequent ATR values are smoothed by Wilder's recurrence:
    ATR_t = (ATR_{t-1} * (period - 1) + TR_t) / period
    """
    if not isinstance(period, int) or isinstance(period, bool) or period <= 0:
        raise ValueError(f"period must be a positive integer >= 1 (got {period} of type {type(period).__name__})")
    clean_h = pd.to_numeric(high, errors="coerce").values
    clean_l = pd.to_numeric(low, errors="coerce").values
    clean_c = pd.to_numeric(close, errors="coerce").values
    n = len(clean_c)

    if n < period or n == 0:
        return pd.Series([np.nan] * n, index=close.index)

    tr = np.empty(n, dtype=np.float64)
    tr[0] = clean_h[0] - clean_l[0]
    for i in range(1, n):
        hl = clean_h[i] - clean_l[i]
        hc = abs(clean_h[i] - clean_c[i - 1])
        lc = abs(clean_l[i] - clean_c[i - 1])
        tr[i] = max(hl, hc, lc)

    atr = np.full(n, np.nan, dtype=np.float64)
    # Seed recurrence with initial SMA of first 'period' true ranges
    atr[period - 1] = float(np.mean(tr[:period]))
    for i in range(period, n):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

    return pd.Series(atr, index=close.index).round(2)


def compute_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Computes all technical indicators and appends them to dataframe."""
    if df is None or df.empty:
        return df.copy() if df is not None else pd.DataFrame()
    out = df.copy()
    if "Date_Str" not in out.columns and "Date" in out.columns:
        out["Date_Str"] = pd.to_datetime(out["Date"]).dt.strftime("%Y-%m-%d")
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
    if df is None or len(df) == 0:
        return TechnicalSummary(
            ticker=ticker,
            last_date="N/A",
            last_close=None,
            total_bars=0,
            is_simulated_demo=is_simulated_demo,
            price_adjustment_basis=price_adjustment_basis,
            currency=currency,
            is_full_52w=False,
            has_adequate_calendar_coverage=False
        )

    if "RSI_14" not in df.columns:
        df = compute_technical_indicators(df)

    if "Date_Str" not in df.columns and "Date" in df.columns:
        df = df.copy()
        df["Date_Str"] = pd.to_datetime(df["Date"]).dt.strftime("%Y-%m-%d")

    n = len(df)
    last_row = df.iloc[-1]
    last_close = float(last_row["Close"]) if pd.notna(last_row.get("Close")) else None
    last_date = str(last_row.get("Date_Str", last_row.get("Date", "N/A")))

    # Multi-period returns: Full N-interval return requires >= N+1 observations
    # R_t(N) = (P_t / P_{t-N} - 1) * 100%
    def get_pct_change(lookback: int) -> Optional[float]:
        if last_close is not None and n >= lookback + 1:
            idx = -1 - lookback
            prior_close = float(df.iloc[idx]["Close"])
            if prior_close > 0:
                return round(((last_close / prior_close) - 1.0) * 100.0, 2)
        return None

    ret_1m = get_pct_change(21)
    ret_3m = get_pct_change(63)
    ret_6m = get_pct_change(126)

    # Duration and calendar coverage evaluation
    has_adequate_calendar_coverage = False
    cov_start_str = None
    cov_end_str = None
    cov_calendar_days = None
    max_gap_days = None

    if n >= 252:
        recent_window = df.tail(252)
        dates_window = pd.to_datetime(recent_window["Date"])
        cov_start_dt = dates_window.iloc[0]
        cov_end_dt = dates_window.iloc[-1]
        cov_start_str = str(recent_window.iloc[0].get("Date_Str", recent_window.iloc[0].get("Date", "N/A")))
        cov_end_str = str(recent_window.iloc[-1].get("Date_Str", recent_window.iloc[-1].get("Date", "N/A")))
        cov_calendar_days = int((cov_end_dt - cov_start_dt).days)

        gaps = dates_window.diff().dt.days.dropna()
        max_gap_days = int(gaps.max()) if len(gaps) > 0 else 0

        # Plausible annual coverage requires 340 to 395 calendar days and max consecutive gap <= 14 days
        if 340 <= cov_calendar_days <= 395 and max_gap_days <= 14:
            has_adequate_calendar_coverage = True
    elif n > 1:
        dates_all = pd.to_datetime(df["Date"])
        cov_start_str = str(df.iloc[0].get("Date_Str", df.iloc[0].get("Date", "N/A")))
        cov_end_str = str(df.iloc[-1].get("Date_Str", df.iloc[-1].get("Date", "N/A")))
        cov_calendar_days = int((dates_all.iloc[-1] - dates_all.iloc[0]).days)
        gaps = dates_all.diff().dt.days.dropna()
        max_gap_days = int(gaps.max()) if len(gaps) > 0 else 0

    # 1-Year Return is only populated if BOTH >= 253 bars (252 return intervals) AND adequate calendar coverage are satisfied
    if n >= 253 and has_adequate_calendar_coverage:
        ret_1y = get_pct_change(252)
        is_full_52w = True
    elif n >= 252 and has_adequate_calendar_coverage:
        ret_1y = None
        is_full_52w = True
    else:
        ret_1y = None
        is_full_52w = False

    # 52-Week High & Low (over available window up to 252 bars)
    w_bars = df.tail(min(252, n))
    high_52w = float(w_bars["High"].max()) if not w_bars.empty and pd.notna(w_bars["High"].max()) else None
    low_52w = float(w_bars["Low"].min()) if not w_bars.empty and pd.notna(w_bars["Low"].min()) else None
    dist_high = round(((last_close / high_52w) - 1.0) * 100.0, 2) if (last_close is not None and high_52w is not None and high_52w > 0) else None
    dist_low = round(((last_close / low_52w) - 1.0) * 100.0, 2) if (last_close is not None and low_52w is not None and low_52w > 0) else None

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
        if last_close is not None and pd.notna(last_row[col]):
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
        # Align strictly on common dates with normalized timestamps
        df_bench_src = df[["Date", "Date_Str", "Close"]].copy()
        df_bench_src["Date"] = pd.to_datetime(df_bench_src["Date"]).dt.normalize()
        df_bench_src = df_bench_src.drop_duplicates(subset=["Date"])

        bm_bench_src = benchmark_df[["Date", "Close"]].copy()
        bm_bench_src["Date"] = pd.to_datetime(bm_bench_src["Date"]).dt.normalize()
        bm_bench_src = bm_bench_src.drop_duplicates(subset=["Date"])

        merged = pd.merge(
            df_bench_src.rename(columns={"Close": "Asset_Close"}),
            bm_bench_src.rename(columns={"Close": "Bench_Close"}),
            on="Date",
            how="inner"
        ).sort_values("Date").reset_index(drop=True)

        # Filter out rows with non-finite or non-positive prices
        merged = merged.dropna(subset=["Asset_Close", "Bench_Close"])
        merged = merged[
            (pd.to_numeric(merged["Asset_Close"], errors="coerce") > 0) &
            (pd.to_numeric(merged["Bench_Close"], errors="coerce") > 0)
        ].reset_index(drop=True)

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

                # Only assign 1-year benchmark change if common overlapping bars >= 253 AND common calendar coverage is adequate
                if common_bars >= 253:
                    common_dates_win = pd.to_datetime(merged["Date"].tail(253))
                    common_cal_days = int((common_dates_win.iloc[-1] - common_dates_win.iloc[0]).days)
                    common_gaps = common_dates_win.diff().dt.days.dropna()
                    common_max_gap = int(common_gaps.max()) if len(common_gaps) > 0 else 0
                    if 340 <= common_cal_days <= 395 and common_max_gap <= 14:
                        win_idx = -253
                        b_win_first = float(merged.iloc[win_idx]["Bench_Close"])
                        a_win_first = float(merged.iloc[win_idx]["Asset_Close"])
                        if b_win_first > 0 and a_win_first > 0:
                            bm_1y = round(((last_b / b_win_first) - 1.0) * 100.0, 2)
                            a_1y = round(((last_a / a_win_first) - 1.0) * 100.0, 2)
                            rel_perf_1y = round(a_1y - bm_1y, 2)

    # Resolve currency honestly: do not assume USD if asset is Indian
    resolved_currency = currency
    indian_syms = {"TCS", "INFY", "HCLTECH", "HINDUNILVR", "BRITANNIA", "DABUR", "MARUTI", "BAJAJ-AUTO", "HEROMOTOCO"}
    if currency == "USD" and (ticker.upper() in indian_syms or ticker.endswith(".NS") or ticker.endswith(".BO")):
        resolved_currency = "INR"

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
        currency=resolved_currency,
        coverage_start_date=cov_start_str,
        coverage_end_date=cov_end_str,
        coverage_calendar_days=cov_calendar_days,
        max_consecutive_gap_days=max_gap_days,
        has_adequate_calendar_coverage=has_adequate_calendar_coverage
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
        vertical_spacing=0.03,
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
        height=490,
        margin=dict(l=35, r=35, t=35, b=25),
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

    df_bench_src = df[["Date", "Close"]].copy()
    df_bench_src["Date"] = pd.to_datetime(df_bench_src["Date"]).dt.normalize()
    df_bench_src = df_bench_src.drop_duplicates(subset=["Date"])

    bm_bench_src = benchmark_df[["Date", "Close"]].copy()
    bm_bench_src["Date"] = pd.to_datetime(bm_bench_src["Date"]).dt.normalize()
    bm_bench_src = bm_bench_src.drop_duplicates(subset=["Date"])

    merged = pd.merge(
        df_bench_src.rename(columns={"Close": "Asset"}),
        bm_bench_src.rename(columns={"Close": "Bench"}),
        on="Date",
        how="inner"
    ).sort_values("Date").reset_index(drop=True)

    # Filter out non-finite or non-positive prices
    merged = merged.dropna(subset=["Asset", "Bench"])
    merged = merged[
        (pd.to_numeric(merged["Asset"], errors="coerce") > 0) &
        (pd.to_numeric(merged["Bench"], errors="coerce") > 0)
    ].reset_index(drop=True)

    if len(merged) < 5:
        return None

    first_asset = float(merged["Asset"].iloc[0])
    first_bench = float(merged["Bench"].iloc[0])
    if first_asset <= 0 or first_bench <= 0 or np.isnan(first_asset) or np.isnan(first_bench):
        return None

    merged["Asset_Norm"] = (merged["Asset"] / first_asset) * 100.0
    merged["Bench_Norm"] = (merged["Bench"] / first_bench) * 100.0

    start_d_str = merged["Date"].iloc[0].strftime("%Y-%m-%d")
    end_d_str = merged["Date"].iloc[-1].strftime("%Y-%m-%d")
    bars_count = len(merged)

    badge = " [SIMULATED DEMO]" if is_simulated_demo else ""
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=merged["Date"], y=merged["Asset_Norm"], name=asset_ticker, line=dict(color="#007AFF", width=2.2)))
    fig.add_trace(go.Scatter(x=merged["Date"], y=merged["Bench_Norm"], name=benchmark_ticker, line=dict(color="#8E8E93", width=1.8, dash="dash")))

    fig.update_layout(
        title=f"Relative Performance vs. {benchmark_ticker} (Base = 100){badge} | {start_d_str} to {end_d_str} ({bars_count} common bars)",
        yaxis=dict(title="Normalized Performance (Base 100)"),
        xaxis=dict(title="Date"),
        height=340,
        margin=dict(l=40, r=40, t=50, b=30),
        template="plotly_white",
        hovermode="x unified"
    )
    return fig
