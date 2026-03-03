import os
import json
import csv
from typing import Dict, Any
from jsonschema import validate

def extract_history_row(
    ts_iso: str, 
    market_state: Dict[str, Any], 
    portfolio_state: Dict[str, Any], 
    decisions: Dict[str, Any], 
    summary: Dict[str, Any]
) -> Dict[str, Any]:
    """Flattens nested states into the history_row schema structure."""
    
    ms_ind = market_state.get("indicators", {})
    ps_sum = portfolio_state.get("portfolio_summary", {})
    
    # Sort exposures
    def get_top_n(exposures_dict: dict, n: int) -> list:
        sorted_items = sorted(exposures_dict.items(), key=lambda x: x[1], reverse=True)
        # Pad with empty data if < n
        sorted_items.extend([("N/A", 0.0)] * (n - len(sorted_items)))
        return sorted_items[:n]
        
    sectors = get_top_n(portfolio_state.get("exposures", {}).get("by_sector", {}), 3)
    regions = get_top_n(portfolio_state.get("exposures", {}).get("by_region", {}), 3)
    
    # Flags
    flags = portfolio_state.get("risk_overlay", {}).get("flags", [])
    missing_count = sum(1 for f in flags if f == "MISSING_ASSET_METADATA")
    
    positions = portfolio_state.get("positions", [])
    opt_count = sum(1 for p in positions if p.get("optionality_consumed", False))
    
    # Decisions
    actions = decisions.get("actions", []) if decisions else []
    add_count = sum(1 for a in actions if a.get("action") == "ADD")
    trim_count = sum(1 for a in actions if a.get("action") == "TRIM")
    sell_count = sum(1 for a in actions if a.get("action") == "EXIT")
    hold_count = sum(1 for a in actions if a.get("action") in ["HOLD", "WATCH"])
    
    row = {
        "timestamp": ts_iso,
        "risk_score": market_state.get("risk_score", 50),
        "color": market_state.get("color", "unknown"),
        
        "liquidity_stress_risk": ms_ind.get("liquidity_stress_risk"),
        "inflation_resurgence_risk": ms_ind.get("inflation_resurgence_risk"),
        "recession_risk": ms_ind.get("recession_risk"),
        "policy_shock_risk": ms_ind.get("policy_shock_risk"),
        
        "hhi": ps_sum.get("hhi", 0.0),
        "top_1_pct": ps_sum.get("top_1_pct", 0.0),
        "top_4_pct": ps_sum.get("top_4_pct", 0.0),
        
        "top_sector_1": sectors[0][0],
        "top_sector_1_weight": sectors[0][1],
        "top_sector_2": sectors[1][0],
        "top_sector_2_weight": sectors[1][1],
        "top_sector_3": sectors[2][0],
        "top_sector_3_weight": sectors[2][1],
        
        "top_region_1": regions[0][0],
        "top_region_1_weight": regions[0][1],
        "top_region_2": regions[1][0],
        "top_region_2_weight": regions[1][1],
        "top_region_3": regions[2][0],
        "top_region_3_weight": regions[2][1],
        
        "flag_missing_metadata_count": missing_count,
        "flag_optionality_consumed_count": opt_count,
        
        "decision_add_count": add_count,
        "decision_trim_count": trim_count,
        "decision_sell_count": sell_count,
        "decision_hold_count": hold_count,
        
        "health_score": summary.get("health_score", 100)
    }
    
    return row

def append_to_history(row: Dict[str, Any]):
    """Appends the formatted row to the history CSV after validation."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schemas", "history_row.schema.json")
    with open(schema_path, "r") as f:
        schema = json.load(f)
        
    validate(instance=row, schema=schema)
        
    history_dir = os.path.join(os.path.dirname(__file__), "..", "..", "out", "history")
    os.makedirs(history_dir, exist_ok=True)
    
    csv_path = os.path.join(history_dir, "history.csv")
    file_exists = os.path.isfile(csv_path)
    
    # We enforce exact column ordering according to the keys in the generated row
    fieldnames = list(row.keys())
    
    with open(csv_path, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerow(row)

def create_run_bundle(
    ts_str: str,
    ts_iso: str,
    snapshot: Dict[str, Any], 
    market_state: Dict[str, Any], 
    portfolio_state: Dict[str, Any], 
    decisions: Dict[str, Any], 
    summary: Dict[str, Any],
    alerts: Dict[str, Any]
) -> str:
    """Creates the deep nested run folder and dumps all artifacts into it."""
    # YYYY/MM/DD/timestampZ
    year = ts_iso[:4]
    month = ts_iso[5:7]
    day = ts_iso[8:10]
    folder_name = ts_iso.replace(":", "").replace("-", "")
    
    base_dir = os.path.join(os.path.dirname(__file__), "..", "..", "out", "runs", year, month, day, folder_name)
    os.makedirs(base_dir, exist_ok=True)
    
    def write_json(name: str, payload: dict):
        with open(os.path.join(base_dir, name), "w") as f:
            json.dump(payload, f, indent=2)
            
    write_json("snapshot.json", snapshot)
    write_json("market_state.json", market_state)
    write_json("portfolio_state.json", portfolio_state)
    write_json(f"decisions.json", decisions)
    write_json(f"summary.json", summary)
    write_json(f"alerts.json", alerts)
    
    return base_dir
