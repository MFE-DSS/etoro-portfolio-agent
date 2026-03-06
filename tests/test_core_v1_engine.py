import pytest
import copy
from src.macro_regime.core_v1_engine import EngineInputs, CoreMacroRegimeEngineV1

@pytest.fixture
def default_goldilocks_inputs():
    return EngineInputs(
        timestamp_utc="2026-03-01T00:00:00Z",
        pmi_level=52.0,
        pmi_trend_3m="up",
        labor_proxy="claims",
        labor_trend="down",
        cpi_yoy=2.1,
        cpi_change_3m="down",
        us2y_level=3.5,
        us2y_trend_2m="down",
        risk_proxy="vix",
        risk_trend="down",
        optional_context_flags={}
    )

def test_goldilocks_regime(default_goldilocks_inputs):
    engine = CoreMacroRegimeEngineV1()
    out, txt = engine.evaluate(default_goldilocks_inputs)
    
    assert out["regime_base"] == "Goldilocks"
    assert out["regime_overlay"] == "None"
    assert out["signals"]["growth_signal"] == "up"
    assert out["signals"]["inflation_signal"] == "down"
    assert out["confidence"] == 85  # 80 + 5 (clean)
    assert out["core_bucket_percent_of_total"] == 80
    assert "Global Equities - Quality" in [x["asset"] for x in out["core_allocation_percent_of_core"]]
    assert sum(x["weight"] for x in out["core_allocation_percent_of_core"]) == 100

def test_recession_overlay(default_goldilocks_inputs):
    engine = CoreMacroRegimeEngineV1()
    inputs = copy.copy(default_goldilocks_inputs)
    # Force recession risk: growth down, risk up
    inputs.pmi_level = 45.0
    inputs.pmi_trend_3m = "down"
    inputs.labor_trend = "up"
    inputs.risk_trend = "up"
    
    out, txt = engine.evaluate(inputs)
    
    assert out["signals"]["growth_signal"] == "down"
    assert out["signals"]["risk_stress"] == True
    assert out["regime_overlay"] == "Recession-risk"
    assert out["confidence"] == 75 # 80 - 10 (risk) + 5 (clean)
    assert out["core_bucket_percent_of_total"] <= 80
    
    alloc_names = [x["asset"] for x in out["core_allocation_percent_of_core"]]
    assert "Cash-like / T-bills" in alloc_names
    assert "Defensive Equities" in alloc_names

def test_mixed_signals(default_goldilocks_inputs):
    engine = CoreMacroRegimeEngineV1()
    inputs = copy.copy(default_goldilocks_inputs)
    # Provide conflicting up/down
    inputs.pmi_trend_3m = "flat"
    inputs.labor_trend = "flat"
    inputs.cpi_change_3m = "flat"
    
    out, txt = engine.evaluate(inputs)
    
    assert out["signals"]["growth_signal"] == "mixed"
    assert out["signals"]["inflation_signal"] == "mixed"
    assert out["regime_base"] == "Transition"
    assert out["confidence"] == 50 # 80 - 15 - 15
    assert out["core_bucket_percent_of_total"] == 60 # Conf < 55
    assert out["risk_controls"]["rebalance_frequency"] == "twice-monthly"

