"""
Writer for the macro_regime_state object.
"""
import json
import os
import logging
from typing import Dict, Any

from src.macro_regime.io.schemas import validate_macro_regime_state

logger = logging.getLogger(__name__)

def write_macro_regime_state(state: Dict[str, Any], output_dir: str, ts_str: str) -> str:
    """Validates and writes the state out to a JSON file."""
    validate_macro_regime_state(state)
    
    os.makedirs(output_dir, exist_ok=True)
    out_file = os.path.join(output_dir, f"macro_regime_state_{ts_str}.json")
    
    with open(out_file, "w") as f:
        json.dump(state, f, indent=2)
        
    logger.info(f"Successfully wrote macro regime state to {out_file}")
    return out_file
