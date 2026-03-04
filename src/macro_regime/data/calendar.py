"""
Handles trading calendar alignment, frequency conversion, and lag logic to strictly avoid look-ahead bias.
"""
import pandas as pd
import numpy as np
from typing import Dict, List
import logging

logger = logging.getLogger(__name__)

def generate_trading_calendar(start_date: str, end_date: str) -> pd.DatetimeIndex:
    """Generate a daily business day calendar, excluding weekends."""
    # For a robust production app, use pandas_market_calendars.
    # Here we stick to BDay as a solid proxy for daily trading calendar.
    return pd.bdate_range(start=start_date, end=end_date)

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
            
        # Timezone naive conversion for safety if needed
        if series.index.tz is not None:
            series.index = series.index.tz_localize(None)
            
        # 1. Shift the index by lag_days
        # For daily data, a shift of +1 day means the value known at T is stamped as available on T+1
        # We add calendar days. 
        shifted_index = series.index + pd.Timedelta(days=lag_days)
        shifted_series = pd.Series(series.values, index=shifted_index)
        
        # Handle duplicates if multiple updates land on the same shifted day (unlikely but possible with weird raw data)
        shifted_series = shifted_series[~shifted_series.index.duplicated(keep='last')]
        
        # 2. Reindex onto the daily trading calendar
        # We use reindex with method='ffill' to carry forward the last KNOWN value.
        # Since the timestamps were already shifted forward into the future by release lag,
        # ffill here only propagates data *after* its official release date proxy.
        aligned_series = shifted_series.reindex(df.index, method='ffill')
        
        df[name] = aligned_series
        
    return df
