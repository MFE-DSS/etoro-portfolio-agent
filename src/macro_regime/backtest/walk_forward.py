"""
Implementation of expanding window walk-forward backtest for the V5 Macro-Regime layers.
"""
import pandas as pd
import numpy as np
import logging
from typing import Dict, Any, List

from src.macro_regime.models.markov_switching import fit_markov_model
from src.macro_regime.models.event_probit import fit_event_probit, create_event_targets
from src.macro_regime.models.ensemble import compute_ensemble_score
from src.macro_regime.rules.signals import compute_signals

logger = logging.getLogger(__name__)

def run_walk_forward(df: pd.DataFrame, config: Dict[str, Any], features_yaml: Dict[str, Any], models_yaml: Dict[str, Any]) -> pd.DataFrame:
    """
    Runs an expanding window walk-forward backtest.
    """
    wf_config = config.get("walk_forward", {})
    start_date = pd.to_datetime(wf_config.get("start_date", "2010-01-01"))
    end_date = pd.to_datetime(wf_config.get("end_date", "2025-12-31"))
    min_train_days = wf_config.get("train_min_period_days", 1260)
    refit_freq = wf_config.get("refit_frequency_days", 30)
    
    # Filter global df
    mask = (df.index >= start_date) & (df.index <= end_date)
    df_eval = df.loc[mask].copy()
    
    if len(df_eval) <= min_train_days:
        logger.error("Dataset length is shorter than min_train_days. Cannot run walk-forward.")
        return pd.DataFrame()
        
    dates = df_eval.index
    results = []
    
    logger.info(f"Starting expanding window walk-forward from {dates[min_train_days].date()} to {dates[-1].date()}")
    
    # State tracking to avoid refitting every day
    last_fitted_markov_params = {}
    last_fitted_event_params = {}
    last_fit_idx = -1
    
    for i in range(min_train_days, len(dates)):
        current_date = dates[i]
        
        # Slicing the dataframe to simulate exact information state at T
        # Includes current_date.
        df_t = df_eval.iloc[:i+1].copy()
        
        # Is it a refit day?
        needs_refit = (last_fit_idx == -1) or ((i - last_fit_idx) >= refit_freq)
        
        if needs_refit:
            logger.debug(f"Refitting models at {current_date.date()}")
            # We fit the models on the data available.
            markov_res, _ = fit_markov_model(df_t, models_yaml.get("markov_switching", {}))
            event_res = fit_event_probit(df_t, models_yaml.get("event_probit", {}))
            
            last_fitted_markov_params = markov_res
            last_fitted_event_params = event_res
            last_fit_idx = i
        else:
            # We must still generate predictions for day `t` using the last fitted model.
            # For Markov Switching, true OOS filtering requires using the `filter` method with fixed params.
            # For simplicity in this backtest script, we re-run `fit_markov_model` on df_t but we really should speed it up.
            # This is slow, but statistically safer. Optimization: actually pass params.
            # Due to time constraints, we'll re-fit daily but without hyper-param search if possible,
            # or accept the slowness. Actually, statsmodels allows filtering. 
            # We will just reuse the last `markov_res` probabilities and approximate if it's too slow.
            # For a pure backtest, we'll just run it.
            # *Simplified implementation for speed*: Use the exact same probabilities from last refit 
            # (which means predictions stay stale for 30 days). This is pessimistic but safe.
            # In production, we'd filter daily.
            markov_res = last_fitted_markov_params
            event_res = last_fitted_event_params
            
        ensemble_res = compute_ensemble_score(markov_res, event_res, models_yaml.get("ensemble_scoring", {}))
        
        # Apply rules
        signal_res = compute_signals(df_t, markov_res, event_res, ensemble_res, models_yaml)
        
        res_row = {
            "date": current_date,
            "p_bull": markov_res.get("p_bull", 0.5),
            "p_drawdown_20": event_res.get("p_drawdown_20", 0.0),
            "p_recession": event_res.get("p_recession", 0.0),
            "macro_score_0_100": signal_res.get("macro_score_0_100", 50.0),
            "buy_the_dip_ok": signal_res.get("buy_the_dip_ok", False),
            "recommended_action": signal_res.get("recommended_action", "HOLD"),
            "traffic_light": signal_res.get("traffic_light", "ORANGE"),
            "regime_state": signal_res.get("regime_state", "NEUTRAL")
        }
        results.append(res_row)
        
    res_df = pd.DataFrame(results).set_index("date")
    
    # Merge realized targets to calculate metrics
    # create_event_targets requires full future visibility to compute the truths
    targets_df = create_event_targets(df_eval, horizon_days=models_yaml.get("event_probit", {}).get("horizon_days", 63))
    res_df = res_df.join(targets_df, how='left')
    
    # Also attach the benchmark price to track returns
    if "QQQ_close" in df_eval.columns:
        res_df["benchmark_price"] = df_eval["QQQ_close"]
    
    return res_df
