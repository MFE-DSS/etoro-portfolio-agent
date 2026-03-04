"""
Ensembles the Markov and Event probabilities into a single $[0,100]$ score and categorical state.
Implements the rules engine for generic macro_regime outputs.
"""
from typing import Dict, Any

def compute_ensemble_score(markov_res: Dict[str, Any], event_res: Dict[str, Any], config: Dict[str, Any]) -> Dict[str, Any]:
    weights = config.get("weights", {})
    w_bull = weights.get("p_bull", 0.4)
    w_dd = weights.get("p_drawdown_20_inv", 0.4)
    w_rec = weights.get("p_recession_inv", 0.2)
    
    p_bull = markov_res.get("p_bull", 0.5)
    p_dd = event_res.get("p_drawdown_20", 0.0)
    p_rec = event_res.get("p_recession", 0.0)
    
    # Score 0-100 logic
    # Higher is better, so we invert drawdown and recession inputs
    score = w_bull * p_bull + w_dd * (1.0 - p_dd) + w_rec * (1.0 - p_rec)
    
    # Normalize weights just in case
    total_w = w_bull + w_dd + w_rec
    score = (score / total_w) * 100.0 if total_w > 0 else 50.0
    
    # Traffic Light mapping
    thresholds = config.get("traffic_light_thresholds", {})
    r_thresh = thresholds.get("red_below", 35.0)
    g_thresh = thresholds.get("green_above", 65.0)
    
    if score <= r_thresh:
        traffic_light = "RED"
        regime_state = "RISK_OFF"
    elif score >= g_thresh:
        traffic_light = "GREEN"
        regime_state = "RISK_ON"
    else:
        traffic_light = "ORANGE"
        regime_state = "NEUTRAL"
        
    return {
        "macro_score_0_100": round(score, 2),
        "traffic_light": traffic_light,
        "regime_state": regime_state
    }
