from typing import Dict, Any, Tuple

def compute_health_score(market_state: Dict[str, Any], portfolio_state: Dict[str, Any], decisions: Dict[str, Any] = None) -> Dict[str, Any]:
    """
    Computes a deterministic health score (0-100) and component breakdowns.
    Penalizes based on concentration, regime mismatch, missing metadata, etc.
    """
    score = 100
    penalties = {}
    top_risks = []
    top_opportunities = []

    # 1. Concentration Penalties
    summary = portfolio_state.get("portfolio_summary", {})
    hhi = summary.get("hhi", 0.0)
    top_4_pct = summary.get("top_4_pct", 0.0)
    
    if hhi > 0.25:
        p = 15
        score -= p
        penalties["high_hhi"] = -p
        top_risks.append("Portfolio is highly concentrated (HHI > 0.25)")
    elif hhi > 0.15:
        p = 5
        score -= p
        penalties["moderate_hhi"] = -p
        
    if top_4_pct > 0.60:
        p = 10
        score -= p
        penalties["high_top_4_pct"] = -p
        top_risks.append("Top 4 positions exceed 60% of portfolio")

    # 2. Regime Mismatch Penalty
    regime = market_state.get("color", "green")
    buckets = portfolio_state.get("risk_overlay", {}).get("correlation_buckets", {})
    cyclical_weight = buckets.get("us_growth", 0.0) + buckets.get("commodities", 0.0) + buckets.get("energy", 0.0)
    
    if regime == "red" and cyclical_weight > 0.40:
        p = 20
        score -= p
        penalties["regime_mismatch_cyclical"] = -p
        top_risks.append("Heavy cyclical weight in a RED risk regime")
    elif regime == "green" and cyclical_weight < 0.20:
        top_opportunities.append("Underweight cyclicals in a GREEN risk regime")

    # 3. Liquidity Stress Penalty
    liquidity_risk = market_state.get("indicators", {}).get("liquidity_stress_risk", 0.0)
    if liquidity_risk > 0.8:
        p = 15
        score -= p
        penalties["extreme_liquidity_stress"] = -p
        top_risks.append("Extreme liquidity stress detected in market")

    # 4. Optionality Consumed Penalty
    positions = portfolio_state.get("positions", [])
    optionality_w = sum(p.get("weight_pct", 0.0) for p in positions if p.get("optionality_consumed", False))
    
    if optionality_w > 0.25:
        p = 10
        score -= p
        penalties["high_optionality_consumed"] = -p
        top_risks.append(f"{optionality_w*100:.1f}% of portfolio weight is in 'optionality consumed' states")

    # 5. Missing Metadata Penalty
    flags = portfolio_state.get("risk_overlay", {}).get("flags", [])
    missing = [f for f in flags if f == "MISSING_ASSET_METADATA"]
    if missing:
        p = 10
        score -= p
        penalties["missing_metadata"] = -p
        top_risks.append("Action required: Map missing tickers in assets.yml")

    # 6. Decision Sanity Penalty (if provided)
    if decisions and regime == "red":
        turnover = sum(a.get("max_change_pct", 0.0) for a in decisions.get("actions", []) if a.get("action") in ["ADD"])
        if turnover > 0.20:
            p = 15
            score -= p
            penalties["high_turnover_red_regime"] = -p
            top_risks.append("Decision engine suggests >20% ADD turnover in a RED regime")

    # Clamping
    score = max(0, min(100, score))

    if score >= 75:
        health_color = "green"
    elif score >= 50:
        health_color = "orange"
    else:
        health_color = "red"

    return {
        "health_score": score,
        "health_color": health_color,
        "breakdown": {
            "base_score": 100,
            "penalties": penalties
        },
        "top_risks": top_risks[:3],         # top 3 limit
        "top_opportunities": top_opportunities[:3]
    }
