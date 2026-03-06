from typing import Dict, Any, List

def compute_alignment(
    target_weights: List[Dict[str, Any]], 
    actual_weights: List[Dict[str, Any]],
    unknown_weight_pct: float,
    regime_base: str,
    regime_overlay: str,
    confidence: int
) -> tuple[List[Dict[str, Any]], str, Dict[str, Any], Dict[str, Any]]:
    
    # 1. Compute gaps
    targets_map = {x["asset"]: x["target"] for x in target_weights}
    actuals_map = {x["asset"]: x["actual"] for x in actual_weights if x["asset"] != "UNKNOWN"}
    
    all_assets = set(targets_map.keys()).union(set(actuals_map.keys()))
    
    gaps = []
    max_trim = 2.5 if confidence < 55 else 5.0
    max_add = 2.5 if confidence < 55 else 5.0
    
    equities_overweight = 0.0
    cash_underweight = 0.0
    
    for asset in all_assets:
        tgt = targets_map.get(asset, 0.0)
        act = actuals_map.get(asset, 0.0)
        gap = act - tgt
        
        action = "HOLD"
        step = 0.0
        
        if gap > 2.0:
            action = "TRIM"
            step = min(gap, max_trim)
        elif gap < -2.0:
            action = "ADD"
            step = min(abs(gap), max_add)
            
        if regime_overlay == "Recession-risk" and "Equities" in asset and action == "ADD":
            action = "HOLD" # cap equities adds
            step = 0.0
            
        if "Equities" in asset and gap > 0:
            equities_overweight += gap
            
        if "Cash-like" in asset and gap < 0:
            cash_underweight += abs(gap)
            
        gaps.append({
            "asset": asset,
            "gap": round(gap, 2),
            "action": action,
            "suggested_step_pct": round(step, 2)
        })
        
    gaps = sorted(gaps, key=lambda x: x["asset"])
    
    # 2. Alignment Quality
    qual = "HIGH"
    if unknown_weight_pct > 5.0:
        qual = "LOW"
    elif unknown_weight_pct > 0.0:
        qual = "MEDIUM"
        
    # 3. Posture Evaluation
    base_posture = "NEUTRAL"
    if regime_base in ["Goldilocks", "Reflation"]:
        base_posture = "RISK_ON"
    elif regime_base == "Disinflation" and confidence >= 75 and regime_overlay != "Recession-risk":
        base_posture = "RISK_ON"
    elif regime_base == "Stagflation":
        base_posture = "RISK_OFF"
        
    if regime_overlay == "Recession-risk" and base_posture == "RISK_ON":
        base_posture = "NEUTRAL"

    conflict = False
    if base_posture in ["RISK_OFF", "NEUTRAL"]:
        if equities_overweight > 10.0 or cash_underweight > 10.0:
            conflict = True
            
    posture_stats = {
        "posture": base_posture,
        "confidence_label": "HIGH" if confidence >= 75 else ("MEDIUM" if confidence >= 55 else "LOW"),
        "posture_conflict": conflict
    }
    
    # 4. Recommendations
    actionable_gaps = [g for g in gaps if g["action"] != "HOLD"]
    actionable_gaps.sort(key=lambda x: abs(x["gap"]), reverse=True)
    top_3 = actionable_gaps[:3]
    
    top_3_out = []
    for g in top_3:
        w_str = f"Overweight target by {g['gap']}%" if g["gap"] > 0 else f"Underweight target by {abs(g['gap'])}%"
        top_3_out.append({
            "action": g["action"],
            "asset": g["asset"],
            "why": w_str
        })
        
    recs = {
        "top_3_actions": top_3_out if top_3_out else [{"action": "HOLD", "asset": "All", "why": "Within tolerance"}],
        "rebalance_style": "MULTI_STEP" if confidence < 55 else "ONE_STEP",
        "notes": []
    }
    if conflict:
        recs["notes"].append("CRITICAL: Severe posture conflict detected. Address risk exposures immediately.")
        
    return gaps, qual, posture_stats, recs

def build_ticker_trades(mapped_positions: List[Dict[str, Any]], gaps: List[Dict[str, Any]], qual: str) -> Dict[str, Any]:
    if qual == "LOW":
        return {"enabled": False, "reason_disabled": "Unknown weight > 5%, unsafe to recommend ticker trades.", "trades": []}
        
    gaps_map = {g["asset"]: g for g in gaps}
    trades = []
    
    # Group tickers by canonical class
    class_tickers = {}
    for pos in mapped_positions:
        cls = pos["asset_class"]
        if cls == "UNKNOWN": continue
        if cls not in class_tickers:
            class_tickers[cls] = []
        class_tickers[cls].append(pos["ticker"])
        
    for cls, gaps_info in gaps_map.items():
        if gaps_info["action"] == "HOLD": continue
        tickers_list = class_tickers.get(cls, [])
        if not tickers_list: continue
        
        side = "SELL" if gaps_info["action"] == "TRIM" else "BUY"
        step = gaps_info["suggested_step_pct"]
        
        # Pro rata equally for MVP
        step_per_ticker = round(step / len(tickers_list), 2)
        if step_per_ticker == 0.0:
            step_per_ticker = 0.01

        for t in tickers_list:
            trades.append({
                "ticker": t,
                "side": side,
                "pct_points": step_per_ticker,
                "mapped_asset": cls
            })
            
    return {"enabled": True, "reason_disabled": None, "trades": trades}
