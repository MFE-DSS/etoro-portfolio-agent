from typing import Dict, Any, List
import yaml
import os
import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def load_alert_rules() -> List[Dict[str, Any]]:
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "alerts.yml")
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("alerts", [])
    except Exception as e:
        logger.warning(f"Could not load alerts.yml: {e}")
        return []

def flatten_metrics(market_state: Dict[str, Any], portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
    """Extracts scalar metrics needed by the alert rules."""
    ms_ind = market_state.get("indicators", {})
    summary = portfolio_state.get("portfolio_summary", {})
    positions = portfolio_state.get("positions", [])
    
    max_pos = max([p.get("weight_pct", 0.0) for p in positions], default=0.0)
    opt_w = sum([p.get("weight_pct", 0.0) for p in positions if p.get("optionality_consumed", False)])
    
    return {
        "risk_score": market_state.get("risk_score", 50),
        "liquidity_stress_risk": ms_ind.get("liquidity_stress_risk", 0.0),
        "top_4_pct": summary.get("top_4_pct", 0.0),
        "max_position_weight": max_pos,
        "optionality_consumed_weight": opt_w,
        "vix": ms_ind.get("vix")
    }

def evaluate_alerts(market_state: Dict[str, Any], portfolio_state: Dict[str, Any]) -> Dict[str, Any]:
    rules = load_alert_rules()
    metrics = flatten_metrics(market_state, portfolio_state)
    
    triggered = []
    
    for rule in rules:
        val = metrics.get(rule["metric"])
        if val is None:
            continue
            
        op = rule.get("operator", ">=")
        threshold = rule.get("threshold", 0.0)
        
        is_triggered = False
        if op == ">=":
            is_triggered = val >= threshold
        elif op == "<=":
            is_triggered = val <= threshold
        elif op == ">":
            is_triggered = val > threshold
        elif op == "<":
            is_triggered = val < threshold
        elif op == "==":
            is_triggered = val == threshold
            
        if is_triggered:
            triggered.append({
                "rule_name": rule["name"],
                "severity": rule.get("severity", "info"),
                "message": rule.get("description", ""),
                "trigger_value": val
            })
            
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "alerts": triggered
    }
