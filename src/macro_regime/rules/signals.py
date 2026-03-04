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
    p_dd = event_res.get("p_drawdown_composite", event_res.get("p_drawdown_20", 0.0))
    traffic_light = ensemble_res.get("traffic_light", "ORANGE")
    
    # --- Sanity Checks & Flags ---
    p_bull = markov_res.get("p_bull", 0.5)
    p_bear = markov_res.get("p_bear", 0.5)
    
    markov_probs_sum = p_bull + p_bear
    markov_is_degenerate = abs(p_bull - 0.5) < 0.02
    events_is_degenerate = event_res.get("p_drawdown_20", 0.0) < 0.005
    dd20_pos_rate = event_res.get("dd20_positive_rate_train", 0.0)
    
    # Missing key features in latest row
    # Just a rough proxy: check how many columns in df are NA for the last row
    latest_row = df.iloc[-1] if not df.empty else pd.Series(dtype=float)
    missing_key_features_count = int(latest_row.isna().sum())
    
    sanity_checks = {
        "markov_probs_sum": float(markov_probs_sum),
        "markov_is_degenerate": bool(markov_is_degenerate),
        "events_is_degenerate": bool(events_is_degenerate),
        "dd20_positive_rate_train": float(dd20_pos_rate),
        "missing_key_features_count": missing_key_features_count
    }
    
    flags = []
    if markov_is_degenerate:
        flags.append("PROBA_DEGENERATE_MARKOV")
    if events_is_degenerate:
        flags.append("PROBA_DEGENERATE_EVENTS")
    if dd20_pos_rate < 0.01:
        flags.append("LOW_POSITIVE_RATE_LABEL")
    if missing_key_features_count > 0:
        flags.append("MISSING_KEY_FEATURES")
        
    is_red_flagged = markov_is_degenerate or events_is_degenerate or missing_key_features_count >= 3
    
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
        
    # Failsafe Override
    if is_red_flagged:
        action = "HOLD"
        dip_ok = False
        
    out = ensemble_res.copy()
    out["buy_the_dip_ok"] = dip_ok
    out["recommended_action"] = action
    out["sanity_checks"] = sanity_checks
    out["signal_flags"] = flags
    
    return out
