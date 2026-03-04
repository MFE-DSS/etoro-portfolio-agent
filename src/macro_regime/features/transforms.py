"""
Defines the registry of available time-series transformations for macroeconomic stationarity.
"""
import pandas as pd
import numpy as np

def transform_log_return(series: pd.Series) -> pd.Series:
    """Computes daily log returns."""
    series = series.replace(0, np.nan)
    return np.log(series / series.shift(1))

def transform_diff(series: pd.Series) -> pd.Series:
    """Computes first differences."""
    return series.diff()

def transform_yoy_pct_change(series: pd.Series) -> pd.Series:
    """
    Computes Year-over-Year percentage change.
    Assuming daily sampling for the aligned series, 1 year ~ 252 trading days.
    """
    return series.pct_change(periods=252)

def transform_level(series: pd.Series) -> pd.Series:
    """Pass-through level variable."""
    return series

def transform_zscore_52w(series: pd.Series) -> pd.Series:
    """
    Rolling 52-week (252 day) Z-score for stationarity.
    Uses expanding down to 63 days to avoid early nulls, but mostly trailing.
    """
    roll = series.rolling(window=252, min_periods=63)
    return (series - roll.mean()) / roll.std().replace(0, np.nan)

def winsorize_series(series: pd.Series, limits=(0.01, 0.01)) -> pd.Series:
    """
    Winsorize a series (clip extreme tails).
    Strictly speaking, quantiles should be computed rolling to avoid look-ahead, 
    but for simplicity and standard practice, we use a trailing 3-year window 
    to determine boundaries.
    """
    roll = series.rolling(window=252 * 3, min_periods=252)
    lower = roll.quantile(limits[0])
    upper = roll.quantile(1.0 - limits[1])
    return series.clip(lower=lower, upper=upper)

TRANSFORMS_REGISTRY = {
    "log_return": transform_log_return,
    "diff": transform_diff,
    "yoy_pct_change": transform_yoy_pct_change,
    "level": transform_level,
    "zscore_52w": transform_zscore_52w
}
