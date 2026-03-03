import os
import csv
import pytest
from src.monitoring.storage import extract_history_row, append_to_history

def test_extract_and_append_history(tmp_path, monkeypatch):
    ts_iso = "2026-03-03T10:00:00+00:00"
    market_state = {
        "risk_score": 60,
        "color": "orange",
        "indicators": {
            "liquidity_stress_risk": 0.5,
            "recession_risk": 0.2
        }
    }
    
    portfolio_state = {
        "portfolio_summary": {"hhi": 0.1, "top_1_pct": 0.2, "top_4_pct": 0.4},
        "exposures": {
            "by_sector": {"Tech": 0.4, "Energy": 0.2},
            "by_region": {"US": 0.8}
        },
        "risk_overlay": {"flags": ["MISSING_ASSET_METADATA"]},
        "positions": [{"optionality_consumed": True}]
    }
    
    decisions = {
        "actions": [
            {"action": "ADD"},
            {"action": "HOLD"}
        ]
    }
    
    summary = {
        "health_score": 85
    }
    
    row = extract_history_row(ts_iso, market_state, portfolio_state, decisions, summary)
    
    assert row["timestamp"] == ts_iso
    assert row["risk_score"] == 60
    assert row["top_sector_1"] == "Tech"
    assert row["top_sector_1_weight"] == 0.4
    assert row["top_sector_3"] == "N/A" # Padded
    assert row["flag_missing_metadata_count"] == 1
    assert row["flag_optionality_consumed_count"] == 1
    assert row["decision_add_count"] == 1
    
    # Test append
    append_to_history(row)
    
    csv_path = os.path.join(os.path.dirname(__file__), "..", "out", "history", "history.csv")
    assert os.path.exists(csv_path)
    
    with open(csv_path, "r") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        assert len(rows) >= 1
        assert rows[-1]["timestamp"] == ts_iso
        assert rows[-1]["top_sector_1"] == "Tech"
