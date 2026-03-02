import pytest
from src.scoring.risk_on_score import calculate_risk_score
from unittest.mock import patch
import json
from jsonschema import validate
from datetime import datetime, timezone
import pandas as pd

@patch('src.indicators.spx_trend.fetch_yahoo_history')
@patch('src.indicators.ndx_trend.fetch_yahoo_history')
@patch('src.indicators.gold_trend.fetch_yahoo_history')
@patch('src.indicators.vix_level.get_latest_price')
@patch('src.indicators.dxy_level.get_latest_price')
@patch('src.indicators.hy_oas_spread.fetch_fred_series')
@patch('src.indicators.us10y_level.fetch_fred_series')
def test_calculate_risk_score(mock_us10y, mock_oas, mock_dxy, mock_vix, mock_gold, mock_ndx, mock_spx):
    # Mock FRED data and simple prices
    mock_us10y.return_value = 4.2
    mock_oas.return_value = 3.5
    mock_dxy.return_value = 104.0
    mock_vix.return_value = 14.5
    
    # Mock DataFrames for MAs
    dates = pd.date_range(start='1/1/2023', periods=200)
    
    df_spx = pd.DataFrame({'Close': [4000 + i for i in range(200)]}, index=dates)
    mock_spx.return_value = df_spx
    
    df_ndx = pd.DataFrame({'Close': [12000 + i*10 for i in range(200)]}, index=dates)
    mock_ndx.return_value = df_ndx
    
    df_gold = pd.DataFrame({'Close': [2000 + i for i in range(200)]}, index=dates)
    mock_gold.return_value = df_gold
    
    # Execute score logic
    state = calculate_risk_score()
    
    # Validate the data output
    assert state['risk_score'] >= 70
    assert state['color'] == 'green'
    assert 'indicators' in state
    assert state['indicators']['vix']['current_vix'] == 14.5
    assert state['indicators']['spx']['above_ma50'] is True
    
    # Validate JSON Schema
    schema_path = "schemas/market_state.schema.json"
    with open(schema_path, "r") as f:
        schema = json.load(f)
        
    state['timestamp'] = datetime.now(timezone.utc).isoformat()
    validate(instance=state, schema=schema)
