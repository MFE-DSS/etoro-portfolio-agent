#!/usr/bin/env python3
"""
CLI entrypoint to run the V5 Macro-Regime econometrics layer.
"""
import os
import sys
import yaml
import json
import logging
import argparse
from datetime import datetime, timezone

from src.macro_regime.data.adapters import get_adapter
from src.macro_regime.features.build_features import build_features
from src.macro_regime.models.markov_switching import fit_markov_model
from src.macro_regime.models.event_probit import fit_event_probit
from src.macro_regime.models.ensemble import compute_ensemble_score
from src.macro_regime.rules.signals import compute_signals
from src.macro_regime.io.writer import write_macro_regime_state

def setup_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(os.path.join(log_dir, f"macro_regime_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")),
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    parser = argparse.ArgumentParser(description="V5 Macro-Regime Layer")
    parser.add_argument("--asof", type=str, help="YYYY-MM-DD", default=datetime.utcnow().strftime("%Y-%m-%d"))
    parser.add_argument("--data-dir", type=str, default="data/")
    parser.add_argument("--out-dir", type=str, default="out/")
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger("run_macro_regime")
    logger.info(f"Starting Macro-Regime calculation as of {args.asof}")
    
    # 1. Load config
    try:
        with open("config/macro_features.yml", "r") as f:
            cfg_feats = yaml.safe_load(f)
        with open("config/macro_models.yml", "r") as f:
            cfg_mods = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configs: {e}")
        sys.exit(1)
        
    start_date = "2000-01-01" # fetch plenty of history for rolling features
    
    # 2. Fetch data (local by default to adhere to constraint)
    raw_data = {}
    for feat in cfg_feats.get("features", []):
        src = feat.get("source", "local")
        adapter = get_adapter(src, args.data_dir)
        try:
            series = adapter.fetch_series(feat["name"], start_date, args.asof)
            raw_data[feat["name"]] = series
        except Exception as e:
            logger.error(f"Failed fetching {feat['name']}: {e}")
            
    # 3. Build features (handles lagging)
    df = build_features(raw_data, cfg_feats, start_date, args.asof)
    
    if df.empty:
        logger.error("Feature dataframe is empty. Cannot proceed.")
        sys.exit(1)
        
    # Stats for output
    missing_days = int(df.isna().all(axis=1).sum())
    
    # 4. Fit Models using all data up to asof_date
    markov_res, _ = fit_markov_model(df, cfg_mods.get("markov_switching", {}))
    event_res = fit_event_probit(df, cfg_mods.get("event_probit", {}))
    
    # 5. Ensemble & Rules
    ensemble_res = compute_ensemble_score(markov_res, event_res, cfg_mods.get("ensemble_scoring", {}))
    final_res = compute_signals(df, markov_res, event_res, ensemble_res, cfg_mods)
    
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_file = ts_iso.replace("-", "").replace(":", "")[:15]
    
    state = {
        "timestamp_utc": ts_iso,
        "asof_date": args.asof,
        "data_coverage": {
            "all_series": {
                "start_date": df.index[0].strftime("%Y-%m-%d") if len(df) > 0 else "1970-01-01",
                "end_date": args.asof,
                "missing_days": missing_days
            }
        },
        "features_summary": {
            "total_features": len(df.columns),
            "transforms_applied": list(set([f.get("transform", "level") for f in cfg_feats.get("features", [])])),
            "lags_applied": [f"{f['name']}:{f.get('release_lag_days', 1)}" for f in cfg_feats.get("features", [])]
        },
        "model_markov": markov_res or {"p_bull":0.5, "p_bear":0.5, "bull_idx":0, "bear_idx":1, "regime_most_likely_idx":0, "most_likely_is_bull":True, "diagnostics":{"loglik":0,"aic":0,"bic":0}, "params":{}, "regime_stats":{"means":[0,0],"variances":[0,0],"mean_variance_switching":True,"switching_variance":True}},
        "model_events": event_res or {"horizon_days":63, "p_drawdown_10":0.0, "p_drawdown_20":0.0, "p_drawdown_composite":0.0, "p_recession":0.0, "dd20_positive_rate_train":0.0, "coefficients":{}, "regularization_C":1.0},
        "aggregate": {
            "macro_score_0_100": final_res.get("macro_score_0_100", 50.0),
            "regime_state": final_res.get("regime_state", "NEUTRAL"),
            "traffic_light": final_res.get("traffic_light", "ORANGE"),
            "buy_the_dip_ok": final_res.get("buy_the_dip_ok", False),
            "recommended_action": final_res.get("recommended_action", "HOLD")
        },
        "sanity_checks": final_res.get("sanity_checks", {
            "markov_probs_sum": 0.0,
            "markov_is_degenerate": True,
            "events_is_degenerate": True,
            "dd20_positive_rate_train": 0.0,
            "missing_key_features_count": 0
        }),
        "flags": ["SUCCESS", "V5_MACRO_ACTIVE"] + final_res.get("signal_flags", [])
    }
    
    if not markov_res or not event_res:
        state["flags"].append("MODEL_FIT_WARN")
        
    write_macro_regime_state(state, args.out_dir, ts_file)

if __name__ == "__main__":
    main()
