from typing import Dict, Any

def compute_exposures(positions: list[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """
    Computes portfolio exposures by sector, region, and asset type.
    Expects a list of position dictionaries containing at least:
    - weight_pct
    - sector (or mapped metadata)
    - region (or mapped metadata)
    - asset_type (or mapped metadata)
    """
    exposures = {
        "by_sector": {},
        "by_region": {},
        "by_asset_type": {}
    }

    for pos in positions:
        weight = pos.get("weight_pct", 0.0)
        
        # Sector
        sector = pos.get("sector", "UNKNOWN")
        exposures["by_sector"][sector] = exposures["by_sector"].get(sector, 0.0) + weight

        # Region
        region = pos.get("region", "UNKNOWN")
        exposures["by_region"][region] = exposures["by_region"].get(region, 0.0) + weight

        # Asset Type
        asset_type = pos.get("asset_type", "UNKNOWN")
        exposures["by_asset_type"][asset_type] = exposures["by_asset_type"].get(asset_type, 0.0) + weight

    return exposures
