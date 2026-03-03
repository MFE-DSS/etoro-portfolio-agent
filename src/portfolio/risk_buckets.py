from typing import Dict, Any

FACTOR_BUCKETS = {
    "energy", "defensives", "quality", "us_growth", 
    "commodities", "rates_sensitive", "other", "unknown"
}

def analyze_risk_buckets(positions: list[Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes portfolio weight aggregated into correlation-risk factor buckets.
    Buckets come from config/assets.yml mapped onto positions.
    """
    buckets = {bucket: 0.0 for bucket in FACTOR_BUCKETS}
    
    for pos in positions:
        weight = pos.get("weight_pct", 0.0)
        bucket = pos.get("factor_bucket", "unknown")
        
        if bucket not in buckets:
            bucket = "unknown"
            
        buckets[bucket] += weight
        
    return buckets
