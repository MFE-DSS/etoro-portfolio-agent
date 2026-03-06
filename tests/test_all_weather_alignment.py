import pytest
import json
import copy

from src.all_weather_alignment.mapper import map_snapshot_to_classes
from src.all_weather_alignment.aggregator import aggregate_actual_weights
from src.all_weather_alignment.target_builder import build_target_weights
from src.all_weather_alignment.reconciler import compute_alignment, build_ticker_trades

@pytest.fixture
def mock_snapshot():
    return {
        "date": "2026-03-01T00:00:00Z",
        "cash_pct": 0.10,
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.40},
            {"ticker": "JNJ", "weight_pct": 0.20},
            {"ticker": "WEIRD_TICKER", "weight_pct": 0.30}
        ]
    }

@pytest.fixture
def mock_assets():
    return {
        "AAPL": {"asset_class_all_weather": "Global Equities - Quality"},
        "JNJ": {"asset_class_all_weather": "Defensive Equities"}
    }
    
@pytest.fixture
def mock_regime():
    return {
        "regime_base": "Reflation",
        "regime_overlay": "None",
        "confidence": 80,
        "core_bucket_percent_of_total": 70,
        "core_allocation_percent_of_core": [
            {"asset": "Global Equities - Quality", "weight": 40},
            {"asset": "Global Equities - Value/Cyclicals", "weight": 30},
            {"asset": "Broad Commodities", "weight": 10},
            {"asset": "Energy Tilt", "weight": 10},
            {"asset": "Cash-like / T-bills", "weight": 10}
        ]
    }

def test_unknown_weight_flagging(mock_snapshot, mock_assets):
    mp, unk, flags = map_snapshot_to_classes(mock_snapshot, mock_assets)
    assert unk == 30.0 # 0.30 * 100
    assert "MISSING_ASSET_METADATA" in flags
    unknown_pos = [p for p in mp if p["asset_class"] == "UNKNOWN"]
    assert len(unknown_pos) == 1
    assert unknown_pos[0]["ticker"] == "WEIRD_TICKER"

def test_alignment_sums_to_100_and_gaps(mock_snapshot, mock_assets, mock_regime):
    # Mapping
    mp, unk, _ = map_snapshot_to_classes(mock_snapshot, mock_assets)
    actuals = aggregate_actual_weights(mp, 0.10)
    
    # AAPL = 40, JNJ = 20, WEIRD = 30(Unknown), Cash = 10
    assert any(x["asset"] == "Global Equities - Quality" and x["actual"] == 40.0 for x in actuals)
    
    # Target
    targets = build_target_weights(mock_regime)
    # Core bucket = 70% of total. 
    # Global Equities Quality target = 40% of 70% = 28%
    assert any(x["asset"] == "Global Equities - Quality" and x["target"] == 28.0 for x in targets)
    
    # Reconciler
    gaps, qual, posture, recs = compute_alignment(
        targets, actuals, unk, 
        mock_regime["regime_base"], mock_regime["regime_overlay"], mock_regime["confidence"]
    )
    
    assert qual == "LOW" # > 5% unknown
    # AAPL gap = 40 (act) - 28 (tgt) = +12. Action: TRIM, step: min(12, 5.0) = 5.0
    aapl_gap = next(g for g in gaps if g["asset"] == "Global Equities - Quality")
    assert aapl_gap["gap"] == 12.0
    assert aapl_gap["action"] == "TRIM"
    assert aapl_gap["suggested_step_pct"] == 5.0
    
    # Conflict: Overweight equities > 10% but base posture is RISK_ON, so conflict is False
    assert posture["posture_conflict"] == False

def test_no_ticker_trades_when_coverage_low(mock_snapshot, mock_assets, mock_regime):
    mp, unk, _ = map_snapshot_to_classes(mock_snapshot, mock_assets)
    actuals = aggregate_actual_weights(mp, 0.10)
    targets = build_target_weights(mock_regime)
    gaps, qual, p, r = compute_alignment(targets, actuals, unk, "Disinflation", "None", 80)
    
    trades = build_ticker_trades(mp, gaps, qual)
    assert trades["enabled"] == False
    assert "Unknown weight > 5%" in trades["reason_disabled"]
    assert len(trades["trades"]) == 0

def test_recommendation_steps_conservative_when_low_confidence(mock_snapshot, mock_assets, mock_regime):
    # Give it 0 unknown weight
    mock_snapshot["positions"] = [{"ticker": "AAPL", "weight_pct": 0.90}]
    mp, unk, _ = map_snapshot_to_classes(mock_snapshot, mock_assets)
    actuals = aggregate_actual_weights(mp, 0.10)
    targets = build_target_weights(mock_regime)
    
    # Force low confidence = 40
    gaps, qual, p, r = compute_alignment(targets, actuals, 0.0, "Reflation", "None", 40)
    
    # Gap will be very large (90 - 28 = +62). Default max trim is 5, but low confidence makes it 2.5
    aapl_gap = next(g for g in gaps if g["asset"] == "Global Equities - Quality")
    assert aapl_gap["suggested_step_pct"] == 2.5
