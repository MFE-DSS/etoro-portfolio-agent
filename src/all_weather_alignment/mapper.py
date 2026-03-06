import yaml
from typing import Dict, Any, List, Tuple

def load_assets_mapping(assets_path: str) -> Dict[str, Any]:
    with open(assets_path, 'r') as f:
        return yaml.safe_load(f)

def map_snapshot_to_classes(snapshot: Dict[str, Any], assets_mapping: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], float, List[str]]:
    """
    Returns: mapped_positions, unknown_weight_pct, flags
    """
    mapped_positions = []
    unknown_weight_pct = 0.0
    flags = []
    
    # Check if cash needs inference or is present
    if "cash_pct" not in snapshot:
        flags.append("CASH_UNKNOWN")
    
    for pos in snapshot.get("positions", []):
        ticker = pos.get("ticker")
        weight = pos.get("weight_pct", 0) * 100 # Convert to 0-100
        
        meta = assets_mapping.get(ticker, {})
        canonical = meta.get("asset_class_all_weather")
        
        if not canonical:
            unknown_weight_pct += weight
            if "MISSING_ASSET_METADATA" not in flags:
                flags.append("MISSING_ASSET_METADATA")
            mapped_positions.append({
                "ticker": ticker,
                "asset_class": "UNKNOWN",
                "weight": weight
            })
        else:
            mapped_positions.append({
                "ticker": ticker,
                "asset_class": canonical,
                "weight": weight
            })
            
    return mapped_positions, unknown_weight_pct, flags
