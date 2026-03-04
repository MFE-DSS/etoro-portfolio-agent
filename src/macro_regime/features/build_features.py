"""
Main feature building orchestrator.
"""
import pandas as pd
import logging
from typing import Dict, Any

from src.macro_regime.data.calendar import align_and_lag_series
from src.macro_regime.features.transforms import TRANSFORMS_REGISTRY, winsorize_series
from src.macro_regime.features.definitions import apply_derived_features, apply_qualitative_dummies

logger = logging.getLogger(__name__)

def build_features(
    raw_series: Dict[str, pd.Series],
    config: Dict[str, Any],
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    1. Aligns and lags raw series to daily trading calendar based on release_lag_days.
    2. Computes derived series before transforms if needed (or implies ordering).
    3. Applies requested stationarity transformations.
    4. Applies dummy logic.
    """
    features_list = config.get("features", [])
    derived_list = config.get("derived", [])
    dummies_list = config.get("qualitative_dummies", [])
    
    logger.info(f"Aligning {len(raw_series)} series to calendar with release lags...")
    df = align_and_lag_series(raw_series, features_list, start_date, end_date)
    
    logger.info("Computing derived baseline series...")
    df = apply_derived_features(df, derived_list)
    
    logger.info("Applying stationarity transformations...")
    # Map back original names to configs for transform
    # Note: If derived series need transforms, we would need them in features_list,
    # but the prompt treats them simply. For robust systems, they share a config list.
    config_map = {f['name']: f for f in features_list}
    
    # Also add derived names to columns if they are to be kept
    for col in list(df.columns):
        if col in config_map:
            trans_name = config_map[col].get("transform", "level")
            trans_func = TRANSFORMS_REGISTRY.get(trans_name)
            if trans_func:
                new_col = f"{col}_{trans_name}" if trans_name != "level" else col
                df[new_col] = trans_func(df[col])
                # We optionally winsorize the transformed version
                if trans_name != "level":
                    df[new_col] = winsorize_series(df[new_col])
                    
    # Generate Rate Momentum proxy if needed by dummy 
    # (hack for "POLICY_TIGHTENING" dummy from prompt)
    if 'DGS2_diff' in df.columns:
        df['DGS2_diff_21d'] = df['DGS2_diff'].rolling(21, min_periods=10).sum()
        
    logger.info("Computing qualitative dummies...")
    df = apply_qualitative_dummies(df, dummies_list)
    
    # Forward fill one last time for safety on the transformed frame 
    # to handle rolling window edge cases safely (without looking ahead)
    df = df.ffill()
    
    return df
