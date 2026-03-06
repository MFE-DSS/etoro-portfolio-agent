from typing import Dict, Any, List

def aggregate_actual_weights(mapped_positions: List[Dict[str, Any]], cash_pct: float) -> List[Dict[str, Any]]:
    agg = {}
    for p in mapped_positions:
        cls = p["asset_class"]
        agg[cls] = agg.get(cls, 0.0) + p["weight"]
        
    cash_val = cash_pct * 100
    if cash_val > 0:
        agg["Cash-like / T-bills"] = agg.get("Cash-like / T-bills", 0.0) + cash_val
        
    # Format as list
    res = [{"asset": k, "actual": round(v, 2)} for k, v in agg.items() if v > 0]
    # Sort for deterministic output
    return sorted(res, key=lambda x: x["asset"])
