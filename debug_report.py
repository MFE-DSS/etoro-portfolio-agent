import json
import os
from src.publish.publish import generate_markdown_report

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

report_path = generate_markdown_report("2026-03-04T120000", summary, alerts, market_state, portfolio_state)
with open(report_path, "r") as f:
    print(f.read())
