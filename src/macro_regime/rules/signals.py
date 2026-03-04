"""
Rules-based signal generation for 'buy the dip' and recommended actions.
"""
from typing import Dict, Any
import pandas as pd

def compute_signals(
    df: pd.DataFrame, 
    markov_res: Dict[str, Any], 
    event_res: Dict[str, Any], 
    ensemble_res: Dict[str, Any],
    config: Dict[str, Any]
) -> Dict[str, Any]:
    
    rules = config.get("rules", {}).get("buy_the_dip", {})
    max_p_rec = rules.get("max_p_recession", 0.4)
    max_p_dd = rules.get("max_p_drawdown", 0.4)
    min_recent_dd = rules.get("min_recent_drawdown", 0.05)
    disallowed_regimes = rules.get("disallowed_regimes", ["RED"])
    
    p_rec = event_res.get("p_recession", 0.0)
    p_dd = event_res.get("p_drawdown_20", 0.0)
    traffic_light = ensemble_res.get("traffic_light", "ORANGE")
    
    # Check if price drawdown from recent peak exceeds X%
    is_dip = False
    if "QQQ_close" in df.columns and not df.empty:
        # Get last 63 days high
        recent_high = df["QQQ_close"].tail(63).max()
        current_price = df["QQQ_close"].iloc[-1]
        
        if recent_high > 0:
            current_dd = 1.0 - (current_price / recent_high)
            is_dip = current_dd >= min_recent_dd
            
    # Check dip conditions
    dip_ok = False
    if is_dip:
        if p_rec <= max_p_rec and p_dd <= max_p_dd:
            if traffic_light not in disallowed_regimes:
                dip_ok = True
                
    action = "HOLD"
    if dip_ok and traffic_light == "GREEN":
        action = "INCREASE_BETA_BUCKET_A"
    elif traffic_light == "RED":
        action = "REDUCE_BETA"
    elif traffic_light == "GREEN":
        action = "NORMAL_EXPOSURE"
        
    out = ensemble_res.copy()
    out["buy_the_dip_ok"] = dip_ok
    out["recommended_action"] = action
    
    return out
