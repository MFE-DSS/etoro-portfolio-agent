"""
Handles generation of summary JSON, CSV dumps, and matplotlib plots for the backtest.
"""
import os
import json
import logging
import pandas as pd
import matplotlib.pyplot as plt
from typing import Dict, Any

logger = logging.getLogger(__name__)

def generate_report(
    res_df: pd.DataFrame, 
    eq_df: pd.DataFrame, 
    cls_metrics: Dict[str, float], 
    strat_stats: Dict[str, float], 
    config: Dict[str, Any]
) -> None:
    rep_conf = config.get("reporting", {})
    out_dir = rep_conf.get("output_dir", "backtests/v5")
    
    os.makedirs(out_dir, exist_ok=True)
    
    summary = {
        "classification": cls_metrics,
        "strategy": strat_stats
    }
    
    sum_path = os.path.join(out_dir, "summary.json")
    with open(sum_path, "w") as f:
        json.dump(summary, f, indent=2)
    logger.info(f"Saved backtest summary to {sum_path}")
        
    if rep_conf.get("save_predictions_csv", True):
        pred_path = os.path.join(out_dir, "predictions.csv")
        res_df.to_csv(pred_path)
        
    if rep_conf.get("save_equity_curve_csv", True):
        eq_path = os.path.join(out_dir, "equity_curve.csv")
        eq_df.to_csv(eq_path)
        
    if rep_conf.get("save_plots", True) and not eq_df.empty:
        plot_path = os.path.join(out_dir, "equity_curve.png")
        
        plt.figure(figsize=(12, 6))
        plt.plot(eq_df.index, eq_df["strategy_cumulative"], label="Strategy (Macro Overlay)")
        plt.plot(eq_df.index, eq_df["benchmark_cumulative"], label="Benchmark (QQQ)", alpha=0.7)
        plt.title("V5 Macro-Regime Rules Strategy vs Benchmark")
        plt.xlabel("Date")
        plt.ylabel("Portfolio Value")
        plt.legend()
        plt.grid(True)
        plt.tight_layout()
        plt.savefig(plot_path)
        plt.close()
        
        logger.info(f"Saved plot to {plot_path}")
