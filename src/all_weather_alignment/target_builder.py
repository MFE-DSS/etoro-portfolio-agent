from typing import Dict, Any, List

def build_target_weights(core_regime: Dict[str, Any]) -> List[Dict[str, Any]]:
    # core_bucket_percent_of_total gives how much of TOTAL portfolio should follow the CORE template.
    # target_total_weight(asset) = core_bucket_percent_of_total/100 * weight/100
    core_pct = core_regime.get("core_bucket_percent_of_total", 0) / 100.0
    
    target_weights = []
    allocs = core_regime.get("core_allocation_percent_of_core", [])
    
    for alloc in allocs:
        asset = alloc["asset"]
        w = alloc["weight"]
        tgt = w * core_pct
        if tgt > 0:
            target_weights.append({
                "asset": asset,
                "target": round(tgt, 2)
            })
        
    return sorted(target_weights, key=lambda x: x["asset"])
