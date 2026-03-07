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
        "indicators": {
            "volatility": {"vix_level": 20.0},
            "recession_risk": 0.15
        },
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
        report_path = pub.generate_markdown_report("2026-03-04T120000", summary, alerts, market_state, portfolio_state, None)

        with open(report_path, "r") as f:
            content = f.read()
        
        print("---START OUTPUT---\n" + content + "\n---END OUTPUT---")
        
        # 1) Check formatting, cash_pct is omitted directly as a pct but exists in Risk Budget
        assert "16%" in content, "cash_pct not formatted correctly in risk budget"
        assert "0.16" not in content, "cash_pct printed as raw float"
        
        # 2) Check regime posture doesn't come from health_score but from heuristic logic because B is unusable
        # market_state risk_score = 62 -> NEUTRAL
        assert "Posture**: **NEUTRAL**" in content
        assert "Wiring Status: V5 Present=Yes, Usable=No" in content
        
        # 3) Check Rationale Section
        assert "3. Rationale (Market Pricing)" in content
        assert "**VIX**: 20.00 vs <20 calm, >25 stress" in content
        
        # 4) Check Sections exist
        assert "4. Regime Risks" in content
        assert "5. What would change my mind?" in content
        
        # Test a healthy V5 scenario
        portfolio_state["risk_overlay"]["macro_regime"]["p_drawdown_20"] = 0.1
        report_path2 = pub.generate_markdown_report("2026-03-04T120001", summary, alerts, market_state, portfolio_state, None)
        with open(report_path2, "r") as f:
            content2 = f.read()
            
        assert "Wiring Status: V5 Present=Yes, Usable=Yes" in content2
        assert "Posture**: **RISK-ON**" in content2

        # Test All-Weather Alignment parsing
        all_weather_alignment = {
            "posture": {"posture": "RISK_OFF", "confidence_label": "HIGH", "posture_conflict": True},
            "brief_bullets": [
                "Derived posture 'RISK_OFF' (HIGH confidence) mapped from regime 'Stagflation'.",
                "CRITICAL: Portfolio alignment strongly diverges from the safety requirements of the active regime.",
                "Alignment Quality is MEDIUM (2.0% of portfolio lacks class mappings)."
            ],
            "recommended_actions": {
                "top_3_actions": [
                    {"action": "TRIM", "asset": "Global Equities - Quality", "why": "Overweight target by 15.0%"}
                ],
                "notes": ["CRITICAL: Severe posture conflict detected. Address risk exposures immediately."]
            }
        }
        
        report_path3 = pub.generate_markdown_report("2026-03-04T120002", summary, alerts, market_state, portfolio_state, all_weather_alignment)
        with open(report_path3, "r") as f:
            content3 = f.read()

        assert "Posture**: **RISK_OFF**" in content3
        assert "Confidence**: High" in content3
        assert "Derived posture 'RISK_OFF'" in content3
        assert "## 0. All-Weather Alignment" in content3
        assert "- CRITICAL: Portfolio alignment strongly diverges" in content3
        assert "- TRIM Global Equities - Quality (Overweight" in content3
        
    finally:
        pub.os.path.join = original_join
