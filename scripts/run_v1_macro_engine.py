import sys
import os
import copy
from datetime import datetime, timezone
import json
import logging
from typing import Dict, Any, Tuple

# Setup local imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.collectors.fred_collector import fetch_all_fred

from src.macro_regime.core_v1_engine import CoreMacroRegimeEngineV1, EngineInputs

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def evaluate_trend(points: list, lookback_days: int) -> str:
    if len(points) < 2:
        return "na"
        
    points = sorted(points, key=lambda p: p.date)
    end_val = points[-1].value
    start_val = None
    
    # Simple search for the lookback target, or just take the oldest available if it's shorter
    target_dt = datetime.fromisoformat(points[-1].date).date() - datetime.timedelta(days=lookback_days)
    
    for p in reversed(points[:-1]):
        p_dt = datetime.fromisoformat(p.date).date()
        if p_dt <= target_dt:
            start_val = p.value
            break
            
    if start_val is None:
        start_val = points[0].value # Not enough history, just use oldest

    if start_val == 0: # Check before division
        if end_val > start_val: return "up"
        if end_val < start_val: return "down"
        return "flat"
        
    diff_pct = (end_val - start_val) / abs(start_val)
    
    if diff_pct > 0.01:
        return "up"
    elif diff_pct < -0.01:
        return "down"
    else:
        return "flat"

def run_engine_live() -> None:
    # 1. Fetch live features from FRED Config mapping
    # Assuming config/macro_features.yml maps:
    # CPIAUCSL -> CPI, ICSA -> Claims, VIXCLS -> VIX, DGS2 -> US2Y, BAMLH0A0HYM2 -> HY OAS
    # USSLIND -> PMI proxy? We need to verify what is in FRED config. Let's look up all series.
    fred_data = fetch_all_fred()
    
    # We will compute the inputs strictly required for V1 engine
    t_now = datetime.now(timezone.utc).isoformat()
    
    # Helper to resolve mapping safely
    def get_latest(keys_to_try: list) -> float:
        for k in keys_to_try:
            if k in fred_data and len(fred_data[k].data) > 0:
                return fred_data[k].data[-1].value
        return None
        
    def get_trend(keys_to_try: list, days: int) -> str:
        for k in keys_to_try:
            if k in fred_data and len(fred_data[k].data) > 0:
                return evaluate_trend(fred_data[k].data, days)
        return "na"

    # Try mapping logical keys typical of existing system
    # PMI
    pmi_lvl = get_latest(["PMI", "USSLIND", "MAN_PMI"]) # Need an ISM/PMI proxy, FRED might just have a coincident indicator
    pmi_trd = get_trend(["PMI", "USSLIND", "MAN_PMI"], 90)
    
    if pmi_lvl is None:
        # Fallback to pure dummy test values if FRED lacks proxy
        logger.warning("No PMI proxy found in FRED config.")
        pmi_lvl = 50.0

    # Labor
    labor_lvl = get_latest(["ICSA", "UNRATE"])
    labor_trd = get_trend(["ICSA", "UNRATE"], 90) # 3M trend
    labor_proxy = "claims" if "ICSA" in fred_data else "nfp" 
    
    # Inflation
    cpi_lvl = get_latest(["CPIAUCSL"])
    cpi_trd = get_trend(["CPIAUCSL"], 90)
    
    # US 2Y
    us2y_lvl = get_latest(["DGS2"])
    us2y_trd = get_trend(["DGS2"], 60) # 2M trend
    
    # Risk
    vix_trd = get_trend(["VIXCLS", "VIX"], 30)
    hy_trd = get_trend(["BAMLH0A0HYM2", "HY_OAS"], 30)
    
    risk_proxy = "vix" if vix_trd != "na" else "hy_oas"
    risk_trd = vix_trd if risk_proxy == "vix" else hy_trd

    inputs = EngineInputs(
        timestamp_utc=t_now,
        pmi_level=pmi_lvl,
        pmi_trend_3m=pmi_trd,
        labor_proxy=labor_proxy,
        labor_trend=labor_trd, # For claims, UP means labor stress. For NFP, UP means labor strong. V1 rules expect UP = stress. 
        cpi_yoy=cpi_lvl,
        cpi_change_3m=cpi_trd,
        us2y_level=us2y_lvl,
        us2y_trend_2m=us2y_trd,
        risk_proxy=risk_proxy,
        risk_trend=risk_trd,
        optional_context_flags={
            "energy_supply_shock": False,
            "major_geopolitical_escalation": False
        }
    )

    # 2. Evaluate
    engine = CoreMacroRegimeEngineV1()
    out, logic = engine.evaluate(inputs)
    
    # 3. Output
    print("\\n=== V1 ENGINE JSON PAYLOAD ===")
    print(json.dumps(out, indent=2))
    print("\\n=== V1 RATIONALE ===")
    for bullet in logic:
         print(f"- {bullet}")

if __name__ == "__main__":
    run_engine_live()
