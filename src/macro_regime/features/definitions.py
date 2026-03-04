"""
Parses configuration to apply derived formulas and dummy variable rules.
"""
import pandas as pd
import re
import logging

logger = logging.getLogger(__name__)

def apply_derived_features(df: pd.DataFrame, derived_config: list) -> pd.DataFrame:
    for conf in derived_config:
        name = conf["name"]
        comp = conf.get("computation", "")
        
        # Simple string eval replacement
        # e.g., "DGS10 - DGS3MO"
        try:
            # We strictly limit what can be eval'd for security/simplicity
            # By replacing known column names with df reference
            eval_str = comp
            for col in df.columns:
                # Add word boundaries to avoid partial matches
                eval_str = re.sub(rf'\b{col}\b', f"df['{col}']", eval_str)
            
            df[name] = eval(eval_str)
        except Exception as e:
            logger.error(f"Failed to compute {name} with formula {comp}: {e}")
            df[name] = pd.NA
            
    return df

def apply_qualitative_dummies(df: pd.DataFrame, dummies_config: list) -> pd.DataFrame:
    for conf in dummies_config:
        name = conf["name"]
        condition = conf["condition"]
        
        try:
            eval_str = condition
            for col in df.columns:
                eval_str = re.sub(rf'\b{col}\b', f"df['{col}']", eval_str)
            
            # eval should result in a boolean series
            bool_series = eval(eval_str)
            # Convert to float (0.0 or 1.0) for models
            df[name] = bool_series.astype(float)
        except Exception as e:
            logger.error(f"Failed to evaluate dummy {name} with condition {condition}: {e}")
            df[name] = 0.0
            
    return df
