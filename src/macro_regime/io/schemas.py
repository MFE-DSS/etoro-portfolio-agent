"""
Validates macro regime state against JSON schema.
"""
import json
import logging
import os
from jsonschema import validate
from typing import Dict, Any

logger = logging.getLogger(__name__)

def validate_macro_regime_state(state: Dict[str, Any]) -> None:
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "schemas", "macro_regime_state.schema.json")
    try:
        with open(schema_path, "r") as f:
            schema = json.load(f)
        validate(instance=state, schema=schema)
        logger.debug("Macro regime state validation successful.")
    except Exception as e:
        logger.error(f"Macro regime state failed schema validation: {e}")
        raise
