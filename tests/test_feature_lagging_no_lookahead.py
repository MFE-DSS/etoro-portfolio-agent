import pytest
import pandas as pd
import numpy as np
from src.macro_regime.data.calendar import align_and_lag_series

def test_align_and_lag_no_lookahead():
    """
    Ensures that a series released on a specific lag is strictly mapped to days 
    after the lag condition is met.
    """
    # Create a monthly series on the 1st of the month
    dates = pd.to_datetime(["2025-01-01", "2025-02-01", "2025-03-01"])
    monthly_series = pd.Series([10.0, 20.0, 30.0], index=dates, name="CPI")
    
    # Configure CPI to have a +15 day release lag
    config = [{"name": "CPI", "release_lag_days": 15}]
    
    raw = {"CPI": monthly_series}
    
    # We test from beginning of Jan to end of Feb
    df = align_and_lag_series(raw, config, "2025-01-01", "2025-02-28")
    
    # Since January's data (2025-01-01 + 15 BUSINESS days = 2025-01-22) isn't known until Jan 22
    # Days before Jan 22 should be NaN.
    
    # 2025-01-21 shouldn't have data
    assert pd.isna(df.loc["2025-01-21", "CPI"])
    
    # 2025-01-22 should have data (10.0)
    assert df.loc["2025-01-22", "CPI"] == 10.0
    
    # 2025-01-31 should still have 10.0
    assert df.loc["2025-01-31", "CPI"] == 10.0
    
    # February's data (2025-02-01 + 15 Bdays = 2025-02-21)
    # On 02-20 it should still be Jan's data
    assert df.loc["2025-02-20", "CPI"] == 10.0
    # On 02-21 it should be Feb's data
    assert df.loc["2025-02-21", "CPI"] == 20.0
