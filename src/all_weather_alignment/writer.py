from typing import Dict, Any, List

def build_alignment_artifact(
    timestamp_utc: str,
    asof_date: str,
    core_regime_ts: str,
    snapshot_ts: str,
    core_regime: Dict[str, Any],
    alignment_quality: Dict[str, Any],
    target_weights: List[Dict[str, Any]],
    actual_weights: List[Dict[str, Any]],
    gaps: List[Dict[str, Any]],
    posture_stats: Dict[str, Any],
    recs: Dict[str, Any],
    ticker_trades: Dict[str, Any]
) -> Dict[str, Any]:
    
    brief_bullets = _build_brief(
        core_regime, 
        alignment_quality, 
        posture_stats, 
        recs, 
        target_weights, 
        actual_weights, 
        ticker_trades
    )
    
    return {
        "timestamp_utc": timestamp_utc,
        "asof_date": asof_date,
        "inputs": {
            "core_regime_timestamp_utc": core_regime_ts,
            "portfolio_snapshot_timestamp_utc": snapshot_ts
        },
        "macro_regime": {
            "regime_base": core_regime.get("regime_base"),
            "regime_overlay": core_regime.get("regime_overlay"),
            "confidence": core_regime.get("confidence"),
            "core_bucket_percent_of_total": core_regime.get("core_bucket_percent_of_total")
        },
        "alignment_quality": alignment_quality,
        "target_weights_total_pct": target_weights,
        "actual_weights_total_pct": actual_weights,
        "gaps_total_pct": gaps,
        "posture": posture_stats,
        "recommended_actions": recs,
        "optional_trade_list": ticker_trades,
        "brief_bullets": brief_bullets
    }

def _build_brief(
    core_regime: Dict[str, Any], 
    quality: Dict[str, Any], 
    posture: Dict[str, Any], 
    recs: Dict[str, Any],
    target: List[Dict[str, Any]],
    actual: List[Dict[str, Any]],
    trades: Dict[str, Any]
) -> List[str]:
    bullets = []
    
    bullets.append(f"Derived posture '{posture['posture']}' ({posture['confidence_label']} confidence) mapped from regime '{core_regime.get('regime_base')}'.")
    
    if posture["posture_conflict"]:
        bullets.append("CRITICAL: Portfolio alignment strongly diverges from the safety requirements of the active regime.")
        
    bullets.append(f"Alignment Quality is {quality['quality_label']} ({quality['unknown_weight_pct']}% of portfolio lacks class mappings).")
    
    actions = recs.get("top_3_actions", [])
    if actions and actions[0]["action"] != "HOLD":
        moves = [f"{a['action']} {a['asset']} ({a['why']})" for a in actions]
        bullets.append("Top adjustments requested: " + "; ".join(moves) + ".")
    else:
        bullets.append("Current portfolio is sufficiently aligned with Core Regime targets; NO immediate class-level repositioning required.")
        
    if trades["enabled"] and trades["trades"]:
        t_list = [f"{t['side']} {t['ticker']} (~{t['pct_points']}%)" for t in trades["trades"][:3]]
        extras = f" and {len(trades['trades']) - 3} others" if len(trades['trades']) > 3 else ""
        bullets.append(f"Suggested execution path: " + ", ".join(t_list) + extras + ".")
        
    return bullets
