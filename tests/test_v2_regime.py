import pytest
import tempfile
import yaml
from datetime import datetime
from src.collectors.config_util import load_config, get_series_for_source
from src.collectors.models import SeriesData, DataPoint
from src.indicators.trend import evaluate_trend
from src.indicators.credit_stress import evaluate_credit_stress
from src.scoring.regime_model import evaluate_regimes_and_scores

def test_config_parsing():
    content = {
        "spx": "YF:^GSPC",
        "us10y": "FRED:DGS10",
        "empty": None
    }
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".yml") as f:
        yaml.dump(content, f)
        temp_name = f.name
        
    config = load_config(temp_name)
    assert config["spx"] == "YF:^GSPC"
    
    fred_series = get_series_for_source("FRED", config)
    assert "us10y" in fred_series
    assert fred_series["us10y"] == "DGS10"
    
    yf_series = get_series_for_source("YF", config)
    assert "spx" in yf_series
    assert yf_series["spx"] == "^GSPC"
    assert "empty" not in yf_series


def test_trend_indicator():
    # Construct 50 points of price = 100 for SPX (so MA is 100).
    # Latest point = 110 (so above MA50 but not enough points for MA200 assumption)
    points = [DataPoint(date=f"2023-01-{i%28+1:02d}", value=100.0) for i in range(49)]
    points.append(DataPoint(date="2023-02-28", value=110.0))
    
    data = {
        "spx": SeriesData(key="spx", data=points)
    }
    
    res = evaluate_trend(data)
    assert "spx" in res
    assert res['spx']['price'] == 110.0
    assert res['spx']['above_ma50'] is True
    # since < 200 points, ma200 defaults to current price, so above_ma200 is False (110 > 110 is False)
    assert res['spx']['above_ma200'] is False

def test_credit_stress_indicator():
    # Under 21 points
    points = [DataPoint(date=f"2023-01-01", value=4.5), DataPoint(date="2023-01-02", value=4.6)]
    data = {"hy_spread": SeriesData(key="hy_spread", data=points)}
    res = evaluate_credit_stress(data)
    assert res['hy_spread_level'] == 4.6
    assert res['hy_spread_change_1m'] is None
    
    # Over 21 points
    points = [DataPoint(date=f"2023-01-{i%28+1:02d}", value=4.0) for i in range(20)]
    points.append(DataPoint(date="2023-02-28", value=5.5))
    data = {"hy_spread": SeriesData(key="hy_spread", data=points)}
    res = evaluate_credit_stress(data)
    assert res['hy_spread_level'] == 5.5
    # The -21st element is the first of the 20 points, since total is 21 points
    assert pytest.approx(res['hy_spread_change_1m'], 0.001) == 1.5

def test_regime_model_aggregation():
    data = {} # Empty data causes all fallbacks to 50 / safe values.
    
    res = evaluate_regimes_and_scores(data)
    assert "risk_score" in res
    assert 0 <= res["risk_score"] <= 100
    assert "color" in res
    assert res["color"] in ["green", "orange", "red"]
    
    # Check sub-scores
    assert "sub_scores" in res
    assert "risk" in res["sub_scores"]
    assert "liquidity" in res["sub_scores"]
    assert res["sub_scores"]["liquidity"]["score"] == 50
    
    # Check probabilities
    assert "regime_probabilities" in res
    assert "recession_risk" in res["regime_probabilities"]
    assert "indicators" in res
    assert "trend" in res["indicators"]
