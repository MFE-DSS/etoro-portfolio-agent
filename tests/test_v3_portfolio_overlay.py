import pytest
from unittest.mock import patch
from datetime import datetime, timezone
from src.portfolio.exposures import compute_exposures
from src.portfolio.concentration import compute_concentration
from src.portfolio.macro_fit import score_macro_fit
from src.portfolio.portfolio_overlay import build_portfolio_state

def test_compute_exposures():
    positions = [
        {"weight_pct": 0.4, "sector": "Technology", "region": "US", "asset_type": "Equity"},
        {"weight_pct": 0.6, "sector": "Technology", "region": "Europe", "asset_type": "Equity"}
    ]
    exposures = compute_exposures(positions)
    
    assert exposures["by_sector"]["Technology"] == 1.0
    assert exposures["by_region"]["US"] == 0.4
    assert exposures["by_region"]["Europe"] == 0.6
    assert exposures["by_asset_type"]["Equity"] == 1.0

def test_compute_concentration():
    positions = [
        {"weight_pct": 0.5},
        {"weight_pct": 0.2},
        {"weight_pct": 0.1},
        {"weight_pct": 0.1},
        {"weight_pct": 0.1}
    ]
    conc = compute_concentration(positions)
    
    # HHI: 0.25 + 0.04 + 0.01 + 0.01 + 0.01 = 0.32
    assert abs(conc["hhi"] - 0.32) < 1e-6
    assert conc["top_1_pct"] == pytest.approx(0.5)
    assert conc["top_4_pct"] == pytest.approx(0.9)
    assert conc["top_10_pct"] == pytest.approx(1.0)

def test_score_macro_fit():
    # Green regime, Cyclical
    res_green_growth = score_macro_fit("AAPL", 0.05, "us_growth", {"color": "green", "indicators": {}})
    assert res_green_growth["macro_fit_score"] == 80
    assert res_green_growth["color"] == "green"
    
    # Red regime, Cyclical (Penalty applied)
    res_red_growth = score_macro_fit("AAPL", 0.05, "us_growth", {"color": "red", "indicators": {}})
    assert res_red_growth["macro_fit_score"] == 30
    assert res_red_growth["color"] == "red"
    
    # Policy shock penalty
    res_shock = score_macro_fit("AAPL", 0.05, "us_growth", {"color": "green", "indicators": {"policy_shock_risk": 0.8}})
    assert res_shock["macro_fit_score"] == 60 # 80 - 20
    
    # Overweight penalties
    res_ow_10 = score_macro_fit("AAPL", 0.12, "us_growth", {"color": "green", "indicators": {}})
    assert res_ow_10["macro_fit_score"] == 70 # 80 - 10
    
    res_ow_15 = score_macro_fit("AAPL", 0.16, "us_growth", {"color": "green", "indicators": {}})
    assert res_ow_15["macro_fit_score"] == 60 # 80 - 20

    # Optionality consumed
    res_opt_regime = score_macro_fit("AAPL", 0.12, "us_growth", {"color": "red", "indicators": {}})
    assert res_opt_regime["optionality_consumed"] is True
    
    res_opt_pnl = score_macro_fit("AAPL", 0.05, "us_growth", {"color": "green", "indicators": {}}, pnl_pct=0.6)
    assert res_opt_pnl["optionality_consumed"] is True


@patch('src.portfolio.portfolio_overlay.load_assets_meta')
def test_build_portfolio_state_mapping_fallback(mock_load):
    # Mock asset metadata with one known (AAPL) and one missing (UNKNOWN_TICKER)
    mock_load.return_value = {
        "AAPL": {"sector": "Technology", "region": "US", "asset_type": "Equity", "factor_bucket": "us_growth"}
    }
    
    snapshot = {
        "cash_pct": 0.1,
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.4, "price": 150},
            {"ticker": "UNKNOWN_TICKER", "weight_pct": 0.5, "price": 100}
        ]
    }
    
    market_state = {
        "color": "green",
        "risk_score": 75,
        "indicators": {}
    }
    
    result = build_portfolio_state(snapshot, market_state)
    
    # 1. Asset Metadata Mapping Fallback
    flags = result["risk_overlay"]["flags"]
    assert "MISSING_ASSET_METADATA" in flags
    
    # Check enriched positions
    pos_unknown = next(p for p in result["positions"] if p["ticker"] == "UNKNOWN_TICKER")
    # Score should be initialized to base neutral (50) and then penalized if overweight
    # 0.5 weight > 0.15 -> -20 penalty -> score 30
    assert pos_unknown["macro_fit_score"] == 30
    
    # Check exposures for UNKNOWN fallback
    assert result["exposures"]["by_sector"]["UNKNOWN"] == 0.5
    assert result["exposures"]["by_sector"]["Technology"] == 0.4
    
    assert "unknown" in result["risk_overlay"]["correlation_buckets"]
    assert result["risk_overlay"]["correlation_buckets"]["unknown"] == 0.5
    assert result["risk_overlay"]["correlation_buckets"]["us_growth"] == 0.4

@patch('src.portfolio.portfolio_overlay.load_assets_meta')
def test_build_portfolio_state_schema_validation(mock_load):
    import json
    from jsonschema import validate
    mock_load.return_value = {
        "AAPL": {"sector": "Technology", "region": "US", "asset_type": "Equity", "factor_bucket": "us_growth"}
    }
    
    snapshot = {
        "timestamp": "2026-03-03T10:00:00Z",
        "cash_pct": 0.1,
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.9, "price": 150}
        ]
    }
    
    market_state = {
        "timestamp": "2026-03-03T10:00:00Z",
        "color": "green",
        "risk_score": 75,
        "indicators": {}
    }
    
    result = build_portfolio_state(snapshot, market_state)
    
    with open("schemas/portfolio_state.schema.json", "r") as f:
        schema = json.load(f)
        
    validate(instance=result, schema=schema)

