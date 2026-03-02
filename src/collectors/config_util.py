import logging
import pandas as pd
from typing import Dict, List, Optional
import yaml
import os

logger = logging.getLogger(__name__)

def load_config(path: str = "config/macro_series.yml") -> Dict[str, str]:
    if not os.path.exists(path):
        logger.warning(f"Config file {path} not found, returning empty dict.")
        return {}
    with open(path, "r") as f:
        return yaml.safe_load(f) or {}

def get_series_for_source(source: str, config: Dict[str, str]) -> Dict[str, str]:
    """Returns {logical_key: external_id} for a specific source like 'FRED'."""
    prefix = f"{source}:"
    result = {}
    for key, val in config.items():
        if val and val.startswith(prefix):
            result[key] = val[len(prefix):]
    return result
