#!/usr/bin/env python3
"""
CLI entrypoint to run the Walk-Forward Backtesting for the V5 Macro-Regime layers.
"""
import os
import sys
import yaml
import logging
import argparse

from src.macro_regime.data.adapters import get_adapter
from src.macro_regime.features.build_features import build_features
from src.macro_regime.backtest.walk_forward import run_walk_forward
from src.macro_regime.backtest.metrics import compute_classification_metrics, simulate_equity_curve
from src.macro_regime.backtest.reporting import generate_report

def setup_logging(log_dir="logs"):
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def main():
    parser = argparse.ArgumentParser(description="V5 Walk-Forward Backtest")
    parser.add_argument("--data-dir", type=str, default="data/")
    args = parser.parse_args()
    
    setup_logging()
    logger = logging.getLogger("run_backtest_v5")
    logger.info(f"Starting V5 Walk-Forward Backtest...")
    
    try:
        with open("config/macro_features.yml", "r") as f:
            cfg_feats = yaml.safe_load(f)
        with open("config/macro_models.yml", "r") as f:
            cfg_mods = yaml.safe_load(f)
        with open("config/backtest.yml", "r") as f:
            cfg_bt = yaml.safe_load(f)
    except Exception as e:
        logger.error(f"Failed to load configs: {e}")
        sys.exit(1)
        
    start_date = "1990-01-01" 
    end_date = cfg_bt.get("walk_forward", {}).get("end_date", "2025-12-31")
    
    # Note: We fetch starting in 1990 or 2000 to have plenty of burn-in for the 5Y initial window
    raw_data = {}
    for feat in cfg_feats.get("features", []):
        src = feat.get("source", "local")
        adapter = get_adapter(src, args.data_dir)
        try:
            series = adapter.fetch_series(feat["name"], start_date, end_date)
            raw_data[feat["name"]] = series
        except Exception as e:
            logger.error(f"Failed fetching {feat['name']}: {e}")
            
    df = build_features(raw_data, cfg_feats, start_date, end_date)
    
    if df.empty:
        logger.error("Feature dataframe is empty.")
        sys.exit(1)
        
    res_df = run_walk_forward(df, cfg_bt, cfg_feats, cfg_mods)
    
    if res_df.empty:
        logger.error("Walk forward returned empty results. Check date ranges.")
        sys.exit(1)
        
    cls_metrics = compute_classification_metrics(res_df)
    eq_df, strat_stats = simulate_equity_curve(res_df, cfg_bt)
    
    generate_report(res_df, eq_df, cls_metrics, strat_stats, cfg_bt)
    
    logger.info("Backtest complete.")

if __name__ == "__main__":
    main()
