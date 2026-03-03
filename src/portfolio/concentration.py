from typing import Dict, Any

def compute_concentration(positions: list[Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes portfolio concentration metrics:
    - HHI (Herfindahl-Hirschman Index)
    - top_1_pct: sum of weight for the top 1 position
    - top_4_pct: sum of weight for the top 4 positions
    - top_10_pct: sum of weight for the top 10 positions
    """
    weights = [pos.get("weight_pct", 0.0) for pos in positions]
    weights.sort(reverse=True)

    # HHI: sum of squared weights (using percentages 0-1 range typically or 0-100. Let's use 0-1 for this system)
    # So if weight is 1.0 (100%), HHI is 1.0. If two weights are 0.5, HHI is 0.5^2 + 0.5^2 = 0.5.
    hhi = sum(w * w for w in weights)

    top_1_pct = sum(weights[:1])
    top_4_pct = sum(weights[:4])
    top_10_pct = sum(weights[:10])

    return {
        "hhi": hhi,
        "top_1_pct": top_1_pct,
        "top_4_pct": top_4_pct,
        "top_10_pct": top_10_pct
    }
