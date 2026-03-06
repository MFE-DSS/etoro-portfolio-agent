#!/usr/bin/env python3
import json
import argparse
import os
from datetime import datetime, timezone

from src.all_weather_alignment.mapper import load_assets_mapping, map_snapshot_to_classes
from src.all_weather_alignment.aggregator import aggregate_actual_weights
from src.all_weather_alignment.target_builder import build_target_weights
from src.all_weather_alignment.reconciler import compute_alignment, build_ticker_trades
from src.all_weather_alignment.writer import build_alignment_artifact

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--core-regime", required=True, help="Path to core_regime_state JSON")
    parser.add_argument("--snapshot", required=True, help="Path to eToro snapshot JSON")
    parser.add_argument("--assets", required=True, help="Path to assets.yml mapping")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    args = parser.parse_args()

    # Read inputs
    with open(args.core_regime, 'r') as f:
        core_regime = json.load(f)
        
    with open(args.snapshot, 'r') as f:
        snapshot = json.load(f)

    assets_map = load_assets_mapping(args.assets)
    
    # 1. Map
    mapped_positions, unknown_pct, flags = map_snapshot_to_classes(snapshot, assets_map)
    
    # 2. Aggregate
    cash_pct = snapshot.get("cash_pct", 0.0)
    actuals = aggregate_actual_weights(mapped_positions, cash_pct)
    
    # 3. Targets
    targets = build_target_weights(core_regime)
    
    # 4. Gaps & Posture
    regime_base = core_regime.get("regime_base", "Transition")
    regime_overlay = core_regime.get("regime_overlay", "None")
    confidence = core_regime.get("confidence", 50)
    
    gaps, qual, posture, recs = compute_alignment(
        targets, actuals, unknown_pct, regime_base, regime_overlay, confidence
    )
    
    # 5. Trades
    trades = build_ticker_trades(mapped_positions, gaps, qual)
    
    # 6. Final Artifact
    t_now = datetime.now(timezone.utc).isoformat()
    # Handle older timestamps vs new cleanly
    try:
        core_ts = core_regime.get("timestamp_utc", t_now)
        snap_ts = snapshot.get("date", t_now)
    except:
        core_ts = t_now
        snap_ts = t_now
        
    qual_dict = {
        "mapping_coverage_pct": round(100.0 - unknown_pct, 2),
        "unknown_weight_pct": round(unknown_pct, 2),
        "quality_label": qual,
        "flags": flags
    }
        
    final_output = build_alignment_artifact(
        t_now, t_now, core_ts, snap_ts, core_regime, qual_dict, targets, actuals, gaps, posture, recs, trades
    )
    
    # Dump
    os.makedirs(args.out_dir, exist_ok=True)
    slug = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    out_path = os.path.join(args.out_dir, f"all_weather_alignment_{slug}.json")
    
    with open(out_path, 'w') as f:
        json.dump(final_output, f, indent=2)
        
    print(f"Alignment Engine completed. Artifact written to {out_path}.")
    print("\\n=== BRIEF BULLETS ===")
    for b in final_output["brief_bullets"]:
        print(f"- {b}")

if __name__ == "__main__":
    main()
