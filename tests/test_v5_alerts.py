from src.monitoring.alerts import evaluate_alerts, load_alert_rules

def test_load_alert_rules():
    rules = load_alert_rules()
    assert len(rules) > 0
    assert any(r["name"] == "risk_score_high" for r in rules)

def test_evaluate_alerts_trigger():
    market_state = {
        "risk_score": 65, # Trigger risk_score_high (>= 60)
        "indicators": {"liquidity_stress_risk": 0.75} # Trigger liquidity_stress (>= 0.70)
    }
    
    portfolio_state = {
        "portfolio_summary": {"top_4_pct": 0.60}, # Trigger concentration_top_4 (>= 0.55)
        "positions": [
            {"weight_pct": 0.25, "optionality_consumed": True} 
            # Trigger single_position_overweight (>= 0.15)
            # Trigger optionality_consumed_heavy (>= 0.20)
        ]
    }
    
    res = evaluate_alerts(market_state, portfolio_state)
    alerts = res["alerts"]
    
    # We expect all 5 predefined rules to hit
    rule_names = [a["rule_name"] for a in alerts]
    assert "risk_score_high" in rule_names
    assert "liquidity_stress" in rule_names
    assert "concentration_top_4" in rule_names
    assert "single_position_overweight" in rule_names
    assert "optionality_consumed_heavy" in rule_names

def test_evaluate_alerts_clean():
    market_state = {
        "risk_score": 50,
        "indicators": {"liquidity_stress_risk": 0.10}
    }
    portfolio_state = {
        "portfolio_summary": {"top_4_pct": 0.20},
        "positions": [{"weight_pct": 0.10, "optionality_consumed": False}]
    }
    res = evaluate_alerts(market_state, portfolio_state)
    assert len(res["alerts"]) == 0
