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
    
    # Simple heuristic mapping for demonstration based on user's assets.yml
    # In a fully fledged setup, this would be fetched from eToro's Discovery API.
    KNOWN_INSTRUMENTS = {
        1265: "AAPL",
        1259: "MSFT",
        1233: "JNJ",
        1118: "XOM",
        1253: "GLD",
        10579: "BTC",
        2507: "TLT",
        8739: "V"
    }

    client_portfolio = raw_data.get("clientPortfolio", {})
    raw_positions = client_portfolio.get("positions", [])
    credit = client_portfolio.get("credit", 0.0)

    total_invested = sum(pos.get("amount", 0.0) for pos in raw_positions)
    total_equity = credit + total_invested
    
    cash_pct = credit / total_equity if total_equity > 0 else 1.0

    normalized_positions = []
    if total_equity > 0:
        # Group by instrument to combine multiple entries of the same ticker
        grouped = {}
        for pos in raw_positions:
            inst_id = pos.get("instrumentID")
            amount = pos.get("amount", 0.0)
            ticker = KNOWN_INSTRUMENTS.get(inst_id, f"ASSET_{inst_id}")
            grouped[ticker] = grouped.get(ticker, 0.0) + amount

        for ticker, amount in grouped.items():
            weight_pct = amount / total_equity
            normalized_positions.append({
                "ticker": ticker,
                "weight_pct": round(weight_pct, 4)
            })

    snapshot = {
        "date": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",
        "cash_pct": round(cash_pct, 4),
        "positions": normalized_positions
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
