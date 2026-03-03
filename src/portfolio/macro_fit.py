from typing import Dict, Any

def score_macro_fit(
    ticker: str,
    weight_pct: float, 
    factor_bucket: str, 
    market_state: Dict[str, Any],
    pnl_pct: float = None
) -> Dict[str, Any]:
    """
    Computes per-position macro_fit_score (0-100), color, optionality flags, and general tags.
    """
    regime_color = market_state.get("color", "orange")
    indicators = market_state.get("indicators", {})
    policy_shock_risk = indicators.get("policy_shock_risk", 0.0)
    
    score = 50 # Default neutral score
    tags = []
    
    # Base scoring based on regime and factor bucket
    if regime_color == "green":
        if factor_bucket in ["us_growth", "commodities", "energy"]:
            score = 80
            tags.append("regime_aligned_cyclical")
        elif factor_bucket in ["defensives"]:
            score = 40
            tags.append("regime_mismatch_defensive")
    elif regime_color == "red":
        if factor_bucket in ["defensives", "quality", "rates_sensitive"]:
            score = 80
            tags.append("regime_aligned_defensive")
        elif factor_bucket in ["us_growth", "commodities", "energy"]:
            score = 30
            tags.append("regime_mismatch_cyclical")
    else: # Neutral (orange)
        # mostly balanced, slight edge to quality
        if factor_bucket == "quality":
            score = 65
        else:
            score = 50
            
    # Policy shock penalty for growth
    if policy_shock_risk > 0.6 and factor_bucket == "us_growth":
        score -= 20
        tags.append("policy_shock_headwind")
        
    # Overweight penalty
    if weight_pct > 0.15:
        score -= 20
        tags.append("severe_overweight")
    elif weight_pct > 0.10:
        score -= 10
        tags.append("overweight")
        
    # Bound score 0-100
    score = max(0, min(100, score))
    
    # Assign color to score
    if score >= 65:
        color = "green"
    elif score >= 40:
        color = "orange"
    else:
        color = "red"
        
    # Heuristics for "optionality consumed"
    # - Overweight cyclical in a risk_off regime
    # - Extended run (high positive PnL)
    optionality_consumed = False
    if regime_color == "red" and factor_bucket in ["us_growth", "commodities"] and weight_pct > 0.10:
        optionality_consumed = True
        tags.append("optionality_consumed_regime")
        
    if pnl_pct is not None and pnl_pct > 0.50: # Arbitrary threshold for extended run
        optionality_consumed = True
        tags.append("optionality_consumed_pnl")

    return {
        "macro_fit_score": score,
        "color": color,
        "optionality_consumed": optionality_consumed,
        "tags": tags
    }
