from src.monitoring.health_score import compute_health_score

def test_health_score_perfect():
    market_state = {"color": "green", "indicators": {"liquidity_stress_risk": 0.1}}
    portfolio_state = {
        "portfolio_summary": {
            "hhi": 0.05,
            "top_4_pct": 0.20
        },
        "risk_overlay": {
            "correlation_buckets": {
                "us_growth": 0.1,
                "commodities": 0.05
            },
            "flags": []
        },
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.1, "optionality_consumed": False}
        ]
    }
    
    score = compute_health_score(market_state, portfolio_state, None)
    assert score["health_score"] == 100
    assert score["health_color"] == "green"
    assert "high_hhi" not in score["breakdown"]["penalties"]

def test_health_score_penalties():
    market_state = {"color": "red", "indicators": {"liquidity_stress_risk": 0.9}}
    portfolio_state = {
        "portfolio_summary": {
            "hhi": 0.30, # -15
            "top_4_pct": 0.65 # -10
        },
        "risk_overlay": {
            "correlation_buckets": {"energy": 0.50}, # -20
            "flags": ["MISSING_ASSET_METADATA"] # -10
        },
        "positions": [
            {"weight_pct": 0.3, "optionality_consumed": True} # -10
        ]
    }
    
    decisions = {
        "actions": [
            {"action": "ADD", "max_change_pct": 0.25} # -15
        ]
    }
    
    score = compute_health_score(market_state, portfolio_state, decisions)
    # Total penalties: -15 (HHI) -10 (Top 4) -20 (cyclical) -15 (liquidity) -10 (opt consumed) -10 (missing) -15 (turnover) = -95
    # Base: 100. Score = 5.
    assert score["health_score"] == 5
    assert score["health_color"] == "red"
    assert score["breakdown"]["penalties"]["high_hhi"] == -15
    assert score["breakdown"]["penalties"]["regime_mismatch_cyclical"] == -20
    assert len(score["top_risks"]) == 3 # Truncated to 3
