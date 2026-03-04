"""
Metrics computation for classification and strategy backtest evaluation.
"""
import pandas as pd
import numpy as np
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
from typing import Dict, Any

def compute_classification_metrics(df: pd.DataFrame) -> Dict[str, float]:
    metrics = {}
    
    # Drawdown metrics
    if "DRAWDOWN_20_FWD" in df.columns and "p_drawdown_20" in df.columns:
        # Drop rows where target is NaN (the future edge)
        valid = df.dropna(subset=["DRAWDOWN_20_FWD", "p_drawdown_20"])
        if len(valid) > 0 and len(valid["DRAWDOWN_20_FWD"].unique()) > 1:
            metrics["dd_auc"] = roc_auc_score(valid["DRAWDOWN_20_FWD"], valid["p_drawdown_20"])
            metrics["dd_brier"] = brier_score_loss(valid["DRAWDOWN_20_FWD"], valid["p_drawdown_20"])
            metrics["dd_logloss"] = log_loss(valid["DRAWDOWN_20_FWD"], valid["p_drawdown_20"])
            
    # Recession metrics
    if "RECESSION_FWD" in df.columns and "p_recession" in df.columns:
        valid = df.dropna(subset=["RECESSION_FWD", "p_recession"])
        if len(valid) > 0 and len(valid["RECESSION_FWD"].unique()) > 1:
            metrics["rec_auc"] = roc_auc_score(valid["RECESSION_FWD"], valid["p_recession"])
            metrics["rec_brier"] = brier_score_loss(valid["RECESSION_FWD"], valid["p_recession"])
            metrics["rec_logloss"] = log_loss(valid["RECESSION_FWD"], valid["p_recession"])
            
    return metrics

def simulate_equity_curve(df: pd.DataFrame, config: Dict[str, Any]) -> pd.DataFrame:
    """
    Simulates a simple strategy switching between market (QQQ) and Risk-Free Rate
    based on the traffic light.
    GREEN: 100% Market
    ORANGE: 50% Market / 50% RF
    RED: 0% Market / 100% RF
    """
    if "benchmark_price" not in df.columns:
        return pd.DataFrame()
        
    init_cap = config.get("strategy", {}).get("initial_capital", 100000.0)
    rf_rate_annual = config.get("strategy", {}).get("risk_free_rate", 0.04)
    rf_daily = (1 + rf_rate_annual) ** (1/252) - 1.0
    
    # Calculate daily market returns
    market_returns = df["benchmark_price"].pct_change().fillna(0)
    
    # Shift exposures by 1 day to simulate taking action AFTER the signal
    # meaning the signal at T dictates the exposure spanning T to T+1
    signals = df["traffic_light"].shift(1).fillna("NEUTRAL") # assume neutral on day 1
    
    exposure = pd.Series(0.5, index=df.index)
    exposure[signals == "GREEN"] = 1.0
    exposure[signals == "RED"] = 0.0
    
    strat_returns = exposure * market_returns + (1.0 - exposure) * rf_daily
    
    # Simulate equity curve
    eq_df = pd.DataFrame(index=df.index)
    eq_df["strategy_cumulative"] = init_cap * (1 + strat_returns).cumprod()
    eq_df["benchmark_cumulative"] = init_cap * (1 + market_returns).cumprod()
    eq_df["exposure"] = exposure
    
    # Compute basic stats
    str_cagr = (eq_df["strategy_cumulative"].iloc[-1] / init_cap) ** (252 / len(df)) - 1
    ben_cagr = (eq_df["benchmark_cumulative"].iloc[-1] / init_cap) ** (252 / len(df)) - 1
    
    str_vol = strat_returns.std() * np.sqrt(252)
    ben_vol = market_returns.std() * np.sqrt(252)
    
    str_sharpe = (str_cagr - rf_rate_annual) / str_vol if str_vol > 0 else 0
    ben_sharpe = (ben_cagr - rf_rate_annual) / ben_vol if ben_vol > 0 else 0
    
    # Max DD
    str_roll_max = eq_df["strategy_cumulative"].cummax()
    str_dd = eq_df["strategy_cumulative"] / str_roll_max - 1
    
    ben_roll_max = eq_df["benchmark_cumulative"].cummax()
    ben_dd = eq_df["benchmark_cumulative"] / ben_roll_max - 1
    
    stats = {
        "strategy_cagr": float(str_cagr),
        "benchmark_cagr": float(ben_cagr),
        "strategy_vol": float(str_vol),
        "benchmark_vol": float(ben_vol),
        "strategy_sharpe": float(str_sharpe),
        "benchmark_sharpe": float(ben_sharpe),
        "strategy_max_dd": float(str_dd.min()),
        "benchmark_max_dd": float(ben_dd.min())
    }
    
    return eq_df, stats
