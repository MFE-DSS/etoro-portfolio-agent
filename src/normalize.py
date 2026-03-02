import os
import json
import logging
import jsonschema
from jsonschema import validate
from datetime import datetime, timezone
from src.utils import get_utc_timestamp, write_json

logger = logging.getLogger(__name__)

def load_schema(schema_path: str = "schemas/snapshot.schema.json") -> dict:
    """Loads the JSON schema for validation."""
    with open(schema_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def normalize_portfolio(raw_data: dict, out_dir: str = "out") -> dict:
    """
    Transforms the raw eToro portfolio data into the stable snapshot schema.
    """
    logger.info("Normalizing raw portfolio data...")
    
    # -------------------------------------------------------------------------
    # NOTE: The actual transformation mapping depends on eToro's JSON structure.
    # Below is a skeletal normalization that conforms to our designed schema.
    # We will refine the keys as we process real payload data.
    # -------------------------------------------------------------------------
    
    # TODO: Perform factual mapping here based on actual `raw_data` keys
    
    snapshot = {
        "date": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",  # Common default
        "cash_pct": 0.05,   # Stub
        "positions": []
    }
    
    schema = load_schema()
    try:
        validate(instance=snapshot, schema=schema)
        logger.info("Normalized snapshot successfully validated against schema.")
    except jsonschema.exceptions.ValidationError as e:
        logger.error(f"Snapshot validation failed: {e}")
        raise
        
    timestamp = get_utc_timestamp()
    filepath = os.path.join(out_dir, f"snapshot_{timestamp}.json")
    write_json(snapshot, filepath)
    
    return snapshot
