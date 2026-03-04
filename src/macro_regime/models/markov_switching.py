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
        
        # Smoothed probabilities per regime (in-sample)
        smoothed = res.smoothed_marginal_probabilities
        # Last date probabilities (as-of end of sample)
        last_probs = smoothed.iloc[-1].to_dict()

        bull_idx = None
        bear_idx = None

        try:
            # Compute weighted means & variances by regime using smoothed probs (robust proxy)
            regime_means = []
            regime_vars = []
            rets = y
            for k in range(k_regimes):
                w = smoothed[k].values.astype(float)
                w = np.clip(w, 1e-6, 1.0)
                w = w / w.sum()
                mu = float(np.sum(w * rets.values))
                var = float(np.sum(w * (rets.values - mu) ** 2))
                regime_means.append(mu)
                regime_vars.append(var)

            if target_trend == 'c':
                bull_idx = int(np.argmax(regime_means))
                bear_idx = int(np.argmin(regime_means))
            else:
                # variance-only proxy
                bull_idx = int(np.argmin(regime_vars))
                bear_idx = int(np.argmax(regime_vars))
        except Exception:
            bull_idx = 0
            bear_idx = 1 if k_regimes > 1 else 0

        # Probabilities as-of last sample date
        p_bull = float(last_probs.get(bull_idx, np.nan))
        p_bear = float(last_probs.get(bear_idx, np.nan))

        # Native most likely regime (argmax) at last date
        # Keep it separate from "bull/bear" mapping to avoid confusion.
        regime_most_likely_idx = int(max(last_probs, key=last_probs.get))
        most_likely_is_bull = bool(regime_most_likely_idx == bull_idx)

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
            "bull_idx": int(bull_idx),
            "bear_idx": int(bear_idx),
            "regime_most_likely_idx": int(regime_most_likely_idx),
            "most_likely_is_bull": most_likely_is_bull,
            "diagnostics": diagnostics,
            "params": params_dict,
            "regime_stats": {
                "means": [float(x) for x in (regime_means if "regime_means" in locals() else [])],
                "variances": [float(x) for x in (regime_vars if "regime_vars" in locals() else [])],
                "mean_variance_switching": bool(target_trend == 'c'),
                "switching_variance": bool(target_variance),
            }
        }
        
        return output, res
        
    except Exception as e:
        logger.error(f"Error fitting Markov model: {e}", exc_info=True)
        return {}, None
