import pytest
import json
import jsonschema
from src.all_weather_alignment.writer import build_alignment_artifact

def test_schema_validation_alignment():
    # Load Schema
    with open("schemas/all_weather_alignment.schema.json", "r") as f:
        schema = json.load(f)
        
    core_regime = {
        "regime_base": "Disinflation",
        "regime_overlay": "None",
        "confidence": 80,
        "core_bucket_percent_of_total": 70
    }
    
    qual = {
        "mapping_coverage_pct": 98.0,
        "unknown_weight_pct": 2.0,
        "quality_label": "MEDIUM",
        "flags": ["MISSING_ASSET_METADATA"]
    }
    
    posture = {
        "posture": "NEUTRAL",
        "confidence_label": "HIGH",
        "posture_conflict": False
    }
    
    recs = {
        "top_3_actions": [{"action": "HOLD", "asset": "All", "why": "Within tolerance"}],
        "rebalance_style": "ONE_STEP",
        "notes": []
    }
    
    trades = {
        "enabled": False,
        "reason_disabled": "User preference",
        "trades": []
    }
    
    # Needs actual keys
    output = build_alignment_artifact(
        "2026-03-01T00:00:00Z",
        "2026-03-01T00:00:00Z",
        "2026-03-01T00:00:00Z",
        "2026-03-01T00:00:00Z",
        core_regime,
        qual,
        [{"asset": "Cash-like / T-bills", "target": 10.0}],
        [{"asset": "Cash-like / T-bills", "actual": 10.0}],
        [{"asset": "Cash-like / T-bills", "gap": 0.0, "action": "HOLD", "suggested_step_pct": 0.0}],
        posture,
        recs,
        trades
    )
    
    jsonschema.validate(instance=output, schema=schema)
