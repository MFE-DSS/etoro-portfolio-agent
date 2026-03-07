"""
normalize.py — Transform raw eToro data into the stable snapshot schema.

Supports two input shapes:
  1. REST API response:
       {"clientPortfolio": {"positions": [...], "credit": <float>}}
     Each position may carry:
       - instrumentID (int) — legacy numeric eToro instrument ID
       - symbol / ticker    — direct string ticker (preferred when present)
       - _csv_ticker        — set by parse_csv_export() fallback
       - amount             — invested value in portfolio currency
       - openRate           — entry price
       - currentRate        — current price (if returned by API)
       - profit             — absolute P&L

  2. Pre-normalized snapshot (dry-mode fixture):
     Already matches the snapshot schema — passed through with re-validation.

Instrument metadata (asset_type, sector, region) is enriched from
config/assets.yml.  Unknown tickers are flagged but not dropped so the
downstream pipeline can still process partial portfolios.

NOTE: The hardcoded KNOWN_INSTRUMENTS dict has been removed.  In production,
instrument names / symbols should come directly from the API response.  If
eToro only returns numeric instrumentIDs without symbols, you should either:
  a) Extend config/assets.yml to add instrumentID → ticker mappings, or
  b) Call the eToro instruments discovery endpoint (api-portal.etoro.com)
     to resolve IDs to symbols at startup.
"""

import os
import json
import logging
import jsonschema
import yaml
from jsonschema import validate
from datetime import datetime, timezone
from src.utils import get_utc_timestamp, write_json

logger = logging.getLogger(__name__)


def load_schema(schema_path: str = "schemas/snapshot.schema.json") -> dict:
    with open(schema_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_assets_config(config_path: str = "config/assets.yml") -> dict:
    if not os.path.exists(config_path):
        return {}
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _build_instrument_id_map(assets_config: dict) -> dict:
    """
    Build an instrumentID → ticker reverse lookup from assets.yml entries
    that carry an 'etoro_instrument_id' field.

    Example assets.yml entry:
      AAPL:
        etoro_instrument_id: 1265
        ...

    This allows users to resolve numeric IDs without hardcoding them here.
    """
    id_map = {}
    for ticker, meta in assets_config.items():
        inst_id = meta.get("etoro_instrument_id")
        if inst_id is not None:
            id_map[int(inst_id)] = ticker
    return id_map


def _resolve_ticker(pos: dict, id_map: dict) -> str:
    """
    Resolve the best available ticker string from a raw position dict.

    Priority order:
      1. symbol / ticker fields (set by newer API versions)
      2. _csv_ticker (set by parse_csv_export)
      3. instrumentID → lookup in id_map (assets.yml etoro_instrument_id)
      4. Fallback placeholder: ASSET_<instrumentID> or UNKNOWN
    """
    for key in ("symbol", "ticker", "instrumentSymbol", "instrument_symbol"):
        val = pos.get(key)
        if val and isinstance(val, str) and val.strip():
            return val.strip().upper()

    csv_ticker = pos.get("_csv_ticker")
    if csv_ticker:
        return csv_ticker.strip().upper()

    inst_id = pos.get("instrumentID")
    if inst_id is not None:
        resolved = id_map.get(int(inst_id))
        if resolved:
            return resolved
        return f"ASSET_{inst_id}"

    return "UNKNOWN"


def _is_pre_normalized(raw_data: dict) -> bool:
    """
    Return True if raw_data already matches the snapshot schema
    (e.g. the dry-mode fixture or a cached snapshot).
    """
    return (
        "positions" in raw_data
        and "cash_pct" in raw_data
        and "date" in raw_data
        and "currency" in raw_data
        and "clientPortfolio" not in raw_data
    )


def normalize_portfolio(raw_data: dict, out_dir: str = "out") -> dict:
    """
    Transform raw eToro data into the validated snapshot schema.

    Handles both REST API responses and pre-normalized fixtures.
    """
    logger.info("Normalizing raw portfolio data...")

    # ---- Pass-through for pre-normalized fixtures -------------------------
    if _is_pre_normalized(raw_data):
        logger.info("Input appears pre-normalized (fixture/cache) — re-validating and returning.")
        schema = load_schema()
        # Strip unknown top-level keys (e.g. 'timestamp' in fixtures) that would
        # fail additionalProperties: false validation.
        known_top_level = set(schema.get("properties", {}).keys())
        clean = {k: v for k, v in raw_data.items() if k in known_top_level}
        try:
            validate(instance=clean, schema=schema)
        except jsonschema.exceptions.ValidationError as e:
            logger.error(f"Pre-normalized snapshot failed schema validation: {e}")
            raise
        timestamp = get_utc_timestamp()
        write_json(clean, os.path.join(out_dir, f"snapshot_{timestamp}.json"))
        return clean

    # ---- REST API / CSV path ---------------------------------------------
    assets_config = load_assets_config()
    id_map = _build_instrument_id_map(assets_config)

    client_portfolio = raw_data.get("clientPortfolio", {})
    raw_positions = client_portfolio.get("positions", [])
    credit = float(client_portfolio.get("credit", 0.0))

    # Aggregate invested value per ticker (multiple positions can share one)
    grouped: dict[str, dict] = {}
    for pos in raw_positions:
        ticker = _resolve_ticker(pos, id_map)
        amount = float(pos.get("amount", 0.0))

        if ticker not in grouped:
            grouped[ticker] = {
                "amount": 0.0,
                "open_rate": pos.get("openRate") or pos.get("open_rate"),
                "current_rate": pos.get("currentRate") or pos.get("current_rate"),
                "profit": 0.0,
            }

        grouped[ticker]["amount"] += amount
        grouped[ticker]["profit"] = grouped[ticker].get("profit", 0.0) + float(
            pos.get("profit", 0.0)
        )
        # Prefer the first open_rate seen (multi-entry positions would need averaging;
        # for now we keep the first as a reasonable approximation)
        if grouped[ticker]["open_rate"] is None:
            grouped[ticker]["open_rate"] = pos.get("openRate") or pos.get("open_rate")
        if grouped[ticker]["current_rate"] is None:
            grouped[ticker]["current_rate"] = pos.get("currentRate") or pos.get("current_rate")

    total_invested = sum(g["amount"] for g in grouped.values())
    total_equity = credit + total_invested
    cash_pct = credit / total_equity if total_equity > 0 else 1.0

    normalized_positions = []
    if total_equity > 0:
        for ticker, agg in grouped.items():
            weight_pct = agg["amount"] / total_equity
            meta = assets_config.get(ticker, {})

            # Compute P&L percentage if we have entry and profit data
            pnl_pct = None
            if agg["amount"] > 0 and agg["profit"] is not None:
                cost_basis = agg["amount"] - agg["profit"]
                if cost_basis > 0:
                    pnl_pct = agg["profit"] / cost_basis

            pos_dict: dict = {
                "ticker": ticker,
                "asset_type": meta.get("asset_type", "Unknown"),
                "region": meta.get("region", "Unknown"),
                "sector": meta.get("sector", "Unknown"),
                "weight_pct": round(weight_pct, 4),
            }

            # Optional fields — only include when data is actually available
            if agg.get("open_rate") is not None:
                pos_dict["avg_open"] = float(agg["open_rate"])
            if agg.get("current_rate") is not None:
                pos_dict["price"] = float(agg["current_rate"])
            if pnl_pct is not None:
                pos_dict["pnl_pct"] = round(pnl_pct, 4)

            if meta.get("asset_type") is None or meta.get("sector") is None:
                logger.warning(
                    f"Ticker '{ticker}' not found in assets.yml — "
                    "add it to config/assets.yml for richer analysis."
                )

            normalized_positions.append(pos_dict)

    snapshot = {
        "date": datetime.now(timezone.utc).isoformat(),
        "currency": "USD",
        "cash_pct": round(cash_pct, 4),
        "positions": normalized_positions,
    }

    schema = load_schema()
    try:
        validate(instance=snapshot, schema=schema)
        logger.info("Normalized snapshot validated successfully.")
    except jsonschema.exceptions.ValidationError as e:
        logger.error(f"Snapshot validation failed: {e}")
        raise

    timestamp = get_utc_timestamp()
    filepath = os.path.join(out_dir, f"snapshot_{timestamp}.json")
    write_json(snapshot, filepath)

    return snapshot
