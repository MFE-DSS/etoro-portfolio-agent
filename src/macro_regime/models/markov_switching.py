"""
Hamilton-style Markov Switching Model implementation using statsmodels.
"""
import pandas as pd
import numpy as np
import statsmodels.api as sm
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def fit_markov_model(df: pd.DataFrame, config: Dict[str, Any]) -> Tuple[Dict[str, Any], Any]:
    """
    Fits a Markov Regression on the target series.
    Returns a dictionary of parameters and probabilities for the LAST observation,
    plus the fitted model object (for plotting or diagnostics).
    """
    target_col = config.get("target_series", "QQQ_close_log_return")
    
    if target_col not in df.columns:
        logger.error(f"Target series {target_col} not found in features.")
        return {}, None
        
    y = df[target_col].dropna()
    
    if len(y) < 252:
        logger.warning("Insufficient data to fit Markov Switching model. Returning empty.")
        return {}, None

    k_regimes = config.get("num_regimes", 2)
    model_type = config.get("model_type", "variance_switching")
    
    # Hamilton 1989 / Markov Regression setup
    target_variance = (model_type in ["variance_switching", "mean_variance_switching"])
    target_trend = 'c' if model_type in ["mean_switching", "mean_variance_switching"] else 'n'
    
    try:
        model = sm.tsa.MarkovRegression(
            y,
            k_regimes=k_regimes,
            trend=target_trend,
            switching_variance=target_variance
        )
        
        # Fit model
        # Search methods like 'ncg' or 'powell' can be more robust than default 'lbfgs'
        method = config.get("search_method", "ncg")
        res = model.fit(method=method, maxiter=config.get("max_iterations", 100), disp=False)
        
        # Determine which regime is bull/bear (or low vol/high vol)
        # We classify regime 0 vs 1 by comparing their smoothed variances.
        # Regime with lower variance is usually the "bull" or "normal" regime.
        if target_variance:
            v0 = res.params.get('sigma2[0]', 0)
            v1 = res.params.get('sigma2[1]', 0)
            bull_idx = 0 if v0 < v1 else 1
        else:
            # If mean switching, use means
            m0 = res.params.get('const[0]', 0)
            m1 = res.params.get('const[1]', 0)
            bull_idx = 0 if m0 > m1 else 1
            
        bear_idx = 1 - bull_idx
        
        # Get smoothed probabilities for the latest date
        latest_probs = res.smoothed_marginal_probabilities.iloc[-1]
        p_bull = float(latest_probs.iloc[bull_idx])
        p_bear = float(latest_probs.iloc[bear_idx])
        regime_label = int(np.argmax([latest_probs.iloc[0], latest_probs.iloc[1]]))
        
        diagnostics = {
            "loglik": float(res.llf),
            "aic": float(res.aic),
            "bic": float(res.bic)
        }
        
        # safely extract params
        params_dict = {k: float(v) for k, v in res.params.items() if not pd.isna(v)}
        
        output = {
            "p_bull": p_bull,
            "p_bear": p_bear,
            "regime_label": regime_label, # Native model label (might not map 1:1 to bull/bear semantically without index lookup, but useful for logs)
            "diagnostics": diagnostics,
            "params": params_dict
        }
        
        return output, res
        
    except Exception as e:
        logger.error(f"Error fitting Markov model: {e}", exc_info=True)
        return {}, None
