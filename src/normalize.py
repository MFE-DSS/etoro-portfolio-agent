"""
src/normalize.py — Transforms raw eToro API payload into the stable snapshot schema.

Responsibilities:
  - Load eToro instrument ID → ticker mapping from config/etoro_instruments.yml
  - Group positions by ticker, computing portfolio weights
  - Enrich each position with metadata from config/assets.yml
  - Validate the resulting snapshot against schemas/snapshot.schema.json
  - Write the snapshot artifact to out/

Unknown instruments: any instrumentID absent from etoro_instruments.yml is logged
as a WARNING and represented as UNMAPPED_<instrumentID>. This keeps the record in
the output (so weight accounting stays consistent) but makes the gap explicit rather
than assigning a meaningless synthetic ticker string.
"""

import logging
import json
import yaml
import jsonschema
from jsonschema import validate
from datetime import datetime, timezone
from typing import Dict, Any

from src.paths import ROOT_DIR, config_path, schema_path, output_path
from src.utils import get_utc_timestamp, write_json
from src.contracts import PortfolioPosition, PortfolioSnapshot

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Config / schema loaders (path-safe, using src.paths)
# ---------------------------------------------------------------------------

def load_instrument_map(path=None) -> Dict[int, str]:
    """
    Loads the eToro instrumentID → ticker mapping from config/etoro_instruments.yml.

    Returns a dict keyed by integer instrument ID.
    Falls back to an empty dict on any load failure so the caller can still
    handle positions (they will all be treated as UNMAPPED).
    """
    _path = path or config_path("etoro_instruments.yml")
    try:
        with open(_path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        mapping = raw.get("instrument_map", {})
        # YAML keys are ints when written as bare integers; ensure that here.
        return {int(k): str(v) for k, v in mapping.items()}
    except FileNotFoundError:
        logger.error(
            f"etoro_instruments.yml not found at {_path}. "
            "All instruments will be treated as UNMAPPED. "
            "Create config/etoro_instruments.yml to fix this."
        )
        return {}
    except Exception as e:
        logger.error(f"Failed to load instrument map from {_path}: {e}")
        return {}


def load_assets_config(path=None) -> Dict[str, Any]:
    """Loads the assets metadata config from config/assets.yml."""
    _path = path or config_path("assets.yml")
    try:
        with open(_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except FileNotFoundError:
        logger.warning(f"assets.yml not found at {_path}. Position enrichment will use defaults.")
        return {}
    except Exception as e:
        logger.warning(f"Failed to load assets config from {_path}: {e}")
        return {}


def load_snapshot_schema(path=None) -> Dict[str, Any]:
    """Loads the JSON schema for snapshot validation."""
    _path = path or schema_path("snapshot.schema.json")
    with open(_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Instrument resolution
# ---------------------------------------------------------------------------

def resolve_ticker(instrument_id: int, instrument_map: Dict[int, str]) -> str:
    """
    Resolves an eToro instrumentID to a ticker symbol.

    If the instrument_id is not in the mapping, logs a WARNING and returns a
    stable, clearly-labelled fallback: UNMAPPED_<instrument_id>.

    The fallback is intentionally NOT a real ticker symbol so that any
    downstream system will notice it rather than silently treating it as a
    valid asset.
    """
    ticker = instrument_map.get(instrument_id)
    if ticker is None:
        fallback = f"UNMAPPED_{instrument_id}"
        logger.warning(
            f"eToro instrumentID {instrument_id} is not present in "
            f"config/etoro_instruments.yml. Representing as '{fallback}'. "
            "Add this instrument to the config file to resolve it properly."
        )
        return fallback
    return ticker


# ---------------------------------------------------------------------------
# Main normalization entry point
# ---------------------------------------------------------------------------

def normalize_portfolio(
    raw_data: dict,
    out_dir: str = None,
    instrument_map_path=None,
    assets_config_path=None,
    schema_path_override=None,
) -> dict:
    """
    Transforms the raw eToro portfolio API payload into the stable snapshot schema.

    Args:
        raw_data: The parsed JSON response from the eToro API.
        out_dir: Directory to write the snapshot artifact. Defaults to <root>/out.
        instrument_map_path: Override for etoro_instruments.yml path (useful in tests).
        assets_config_path: Override for assets.yml path (useful in tests).
        schema_path_override: Override for snapshot.schema.json path (useful in tests).

    Returns:
        The validated snapshot dict.
    """
    logger.info("Normalizing raw eToro portfolio data...")

    _out_dir = out_dir or str(output_path(""))  # output_path("") gives <root>/out/

    instrument_map = load_instrument_map(instrument_map_path)
    assets_config = load_assets_config(assets_config_path)

    client_portfolio = raw_data.get("clientPortfolio", {})
    raw_positions = client_portfolio.get("positions", [])
    credit = float(client_portfolio.get("credit", 0.0))

    total_invested = sum(float(pos.get("amount", 0.0)) for pos in raw_positions)
    total_equity = credit + total_invested

    cash_pct = credit / total_equity if total_equity > 0 else 1.0

    normalized_positions = []

    if total_equity > 0:
        # Group by resolved ticker to merge multiple positions in the same instrument
        grouped: Dict[str, float] = {}
        for pos in raw_positions:
            inst_id = pos.get("instrumentID")
            amount = float(pos.get("amount", 0.0))
            ticker = resolve_ticker(int(inst_id), instrument_map)
            grouped[ticker] = grouped.get(ticker, 0.0) + amount

        for ticker, amount in grouped.items():
            weight_pct = amount / total_equity

            asset_info = assets_config.get(ticker, {})
            asset_type = asset_info.get("asset_type", "Unknown")
            region = asset_info.get("region", "Unknown")
            sector = asset_info.get("sector", "Unknown")

            # Warn when an UNMAPPED ticker has no metadata either — double gap
            if ticker.startswith("UNMAPPED_") and not asset_info:
                logger.warning(
                    f"Position '{ticker}' has no metadata in assets.yml. "
                    "It will appear with Unknown asset_type/region/sector."
                )

            normalized_positions.append(PortfolioPosition(
                ticker=ticker,
                asset_type=asset_type,
                region=region,
                sector=sector,
                weight_pct=round(weight_pct, 4),
            ))

    typed_snapshot = PortfolioSnapshot(
        date=datetime.now(timezone.utc).isoformat(),
        currency="USD",
        cash_pct=round(cash_pct, 4),
        positions=normalized_positions,
    )
    snapshot = typed_snapshot.to_dict()

    # Schema validation
    _schema_path = schema_path_override or schema_path("snapshot.schema.json")
    try:
        schema = load_snapshot_schema(_schema_path)
        validate(instance=snapshot, schema=schema)
        logger.info("Normalized snapshot successfully validated against schema.")
    except jsonschema.exceptions.ValidationError as e:
        logger.error(f"Snapshot validation failed: {e}")
        raise

    # Persist artifact
    timestamp = get_utc_timestamp()
    import os
    filepath = os.path.join(str(_out_dir), f"snapshot_{timestamp}.json")
    write_json(snapshot, filepath)

    return snapshot
