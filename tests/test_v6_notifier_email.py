import pytest
from src.publish.publish import generate_markdown_report

def test_generate_markdown_report_formatting(tmp_path):
    # Mock artifacts
    summary = {
        "health_score": 30,
        "health_color": "red",
        "penalties": {"Drawdown": 70},
        "top_risks": ["Test Risk"]
    }
    alerts = {"alerts": []}
    market_state = {
        "risk_score": 62,
        "color": "orange",
        "sub_scores": {"inflation": {"score": 80, "color": "orange"}},
        "indicators": {"VIX": 20.0, "recession_risk": 0.15},
        "regime_probabilities": {"bull": 0.6}
    }
    portfolio_state = {
        "cash_pct": 0.1643,
        "portfolio_summary": {"cash_pct": 0.1643, "hhi": 0.10},
        "risk_overlay": {
            "macro_regime": {
                "regime_state": "RISK_ON",
                "macro_score": 80.0,
                "traffic_light": "GREEN",
                "p_bull": 0.8,
                "p_drawdown_10": 0.0,
                "p_drawdown_20": 0.0,
                "p_drawdown_composite": 0.0,
                "buy_the_dip_ok": True,
                "recommended_action": "INCREASE_BETA_BUCKET_A"
            },
            "flags": ["MISSING_ASSET_METADATA", "PROBA_DEGENERATE_EVENTS"]
        },
        "positions": []
    }

    # Generate
    report_file = tmp_path / "test_report.md"
    
    # Let's monkeypatch os.path.dirname to put it in tmp_path
    import os
    original_join = os.path.join
    def mock_join(*args):
        if "report_" in args[-1]:
            return str(report_file)
        return original_join(*args)
    
    import src.publish.publish as pub
    pub.os.path.join = mock_join
    
    try:
        report_path = pub.generate_markdown_report("2026-03-04T120000", summary, alerts, market_state, portfolio_state)

        with open(report_path, "r") as f:
            content = f.read()
        
        print("---START OUTPUT---\n" + content + "\n---END OUTPUT---")
        
        # 1) Check cash percentage formatting
        assert "16.4%" in content, "cash_pct not formatted correctly"
        assert "0.16" not in content, "cash_pct printed as raw float"
        
        # 2) Check regime headline relies on V5 state (which is UNKNOWN due to degeneracy)
        # Why is it degenerate? Because p_drawdown_20 and p_drawdown_10 are both 0.0
        assert "V5 status: DEGRADED (probabilities degenerate)" in content
        assert "Target Posture**: UNKNOWN" in content
        
        # 3) Check that Macro Regime is printed
        assert "B) Macro Regime" in content
        
        # 4) Check C Market State formatted correctly
        assert "Heuristic Score**: 62" in content
        assert "15.0%" in content # recession_risk
        assert "60.0%" in content # regime_probabilities bull
        
        # Test a healthy V5 scenario
        portfolio_state["risk_overlay"]["macro_regime"]["p_drawdown_20"] = 0.1
        report_path2 = pub.generate_markdown_report("2026-03-04T120001", summary, alerts, market_state, portfolio_state)
        with open(report_path2, "r") as f:
            content2 = f.read()
            
        assert "V5 status: DEGRADED" not in content2
        assert "Target Posture**: RISK_ON" in content2
        
    finally:
        pub.os.path.join = original_join
