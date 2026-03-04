"""
Handles trading calendar alignment, frequency conversion, and lag logic to strictly avoid look-ahead bias.
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

from pandas.tseries.offsets import BDay

DEFAULT_TZ = "UTC"

def _ensure_datetime_index(series: pd.Series) -> pd.Series:
    s = series.copy()
    if not isinstance(s.index, pd.DatetimeIndex):
        s.index = pd.to_datetime(s.index)
    # Normalize to midnight to avoid accidental time drift across joins
    if s.index.tz is not None:
        s.index = s.index.tz_convert(None)
    s.index = s.index.normalize()
    return s.sort_index()

def _shift_index_business_days(idx: pd.DatetimeIndex, lag_days: int) -> pd.DatetimeIndex:
    """
    Apply conservative availability lag in BUSINESS DAYS (not calendar days),
    so that weekend/holiday effects do not create inconsistent effective lags.
    """
    if lag_days <= 0:
        return idx
    return (idx + BDay(lag_days)).normalize()

def generate_trading_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """Generate a daily business day calendar, excluding weekends."""
    idx = pd.bdate_range(start=start_date, end=end_date)
    return idx.normalize()

def align_and_lag_series(
    raw_data: Dict[str, pd.Series],
    features_config: List[Dict],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    Given raw time series with heterogeneous frequencies (daily, weekly, monthly),
    align them to a common daily trading calendar while applying the required `release_lag_days`
    to guarantee no look-ahead bias out of sample.
    """
    calendar = generate_trading_calendar(start_date, end_date)
    df = pd.DataFrame(index=calendar)
    
    config_map = {f['name']: f for f in features_config}
    
    for name, series in raw_data.items():
        if series.empty:
            logger.warning(f"Series {name} is empty. Adding NaN column.")
            df[name] = np.nan
            continue
            
        conf = config_map.get(name)
        if not conf:
            logger.warning(f"Config for {name} missing during alignment. Using default lag 1.")
            lag_days = 1
        else:
            lag_days = conf.get("release_lag_days", 1)
            
        s = _ensure_datetime_index(series)
            
        # 1. Shift the index by lag_days using BUSINESS DAYS
        if lag_days > 0:
            shifted_index = _shift_index_business_days(s.index, int(lag_days))
            shifted_series = pd.Series(s.values, index=shifted_index)
        else:
            shifted_series = pd.Series(s.values, index=s.index)
            
        # Handle duplicates
        shifted_series = shifted_series[~shifted_series.index.duplicated(keep='last')]
        shifted_series = shifted_series.sort_index()
        
        # 2. Reindex onto the daily trading calendar
        aligned_series = shifted_series.reindex(df.index, method='ffill')
        
        df[name] = aligned_series
        
    return df
