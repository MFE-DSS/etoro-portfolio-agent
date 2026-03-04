from typing import Dict, Any
from datetime import datetime, timezone
import yaml
import os

from src.portfolio.exposures import compute_exposures
from src.portfolio.concentration import compute_concentration
from src.portfolio.risk_buckets import analyze_risk_buckets
from src.portfolio.macro_fit import score_macro_fit

def load_assets_meta() -> Dict[str, Any]:
    """Loads the assets configuration mapping."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "assets.yml")
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load assets.yml: {e}")
        return {}

def build_portfolio_state(snapshot: Dict[str, Any], market_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Orchestrates the Portfolio Overlay logic (V3).
    Expects normalized eToro snapshot and V2 market state.
    """
    assets_meta = load_assets_meta()
    
    raw_positions = snapshot.get("positions", [])
    
    # Enrich positions with mapped metadata and score them
    enriched_positions = []
    flags = set()
    
    for pos in raw_positions:
        ticker = pos.get("ticker", "UNKNOWN")
        meta = assets_meta.get(ticker)
        
        if not meta:
            flags.add("MISSING_ASSET_METADATA")
            # Create a placeholder enriched position
            enriched_pos = {
                **pos,
                "ticker": ticker,
                "weight_pct": pos.get("weight_pct", 0.0),
                "sector": "UNKNOWN",
                "region": "UNKNOWN",
                "asset_type": "UNKNOWN",
                "role": "core",
                "factor_bucket": "unknown",
                "pnl_pct": pos.get("pnl_pct", 0.0)
            }
        else:
            enriched_pos = {
                **pos, # Keep original fields
                "sector": meta.get("sector", "UNKNOWN"),
                "region": meta.get("region", "UNKNOWN"),
                "asset_type": meta.get("asset_type", "UNKNOWN"),
                "role": meta.get("role", "core"),
                "factor_bucket": meta.get("factor_bucket", "unknown"),
            }
            
        enriched_positions.append(enriched_pos)

    # 1. Calculate exposures based on mapped metadata
    exposures = compute_exposures(enriched_positions)
    
    # 2. Calculate concentration
    concentration = compute_concentration(enriched_positions)
    
    # 3. Calculate risk buckets based on mapped metadata
    correlation_buckets = analyze_risk_buckets(enriched_positions)
    
    # 4. Score macro fit per position
    final_positions = []
    for pos in enriched_positions:
        score_res = score_macro_fit(
            ticker=pos["ticker"],
            weight_pct=pos.get("weight_pct", 0.0),
            factor_bucket=pos.get("factor_bucket", "unknown"),
            market_state=market_state,
            pnl_pct=pos.get("pnl_pct")
        )
        
        final_positions.append({
            "ticker": pos["ticker"],
            "weight_pct": pos.get("weight_pct", 0.0),
            "macro_fit_score": score_res["macro_fit_score"],
            "color": score_res["color"],
            "optionality_consumed": score_res["optionality_consumed"],
            "tags": score_res["tags"]
        })

    # Assemble V5 aware risk_overlay
    macro_regime_payload = market_state.get("macro_regime", {
        "regime_state": "UNKNOWN",
        "macro_score": 50.0,
        "traffic_light": market_state.get("color", "unknown").upper(),
        "p_drawdown_10": 0.0,
        "p_drawdown_20": 0.0,
        "p_drawdown_composite": 0.0,
        "p_bull": 0.5,
        "buy_the_dip_ok": False,
        "recommended_action": "HOLD"
    })

    # Assemble final payload
    portfolio_state = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "portfolio_summary": {
            "total_positions": len(final_positions),
            "cash_pct": snapshot.get("cash_pct", 0.0),
            **concentration
        },
        "exposures": exposures,
        "risk_overlay": {
            "macro_regime": macro_regime_payload,
            "correlation_buckets": correlation_buckets,
            "flags": list(flags)
        },
        "positions": final_positions
    }
    
    return portfolio_state
