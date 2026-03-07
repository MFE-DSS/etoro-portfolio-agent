"""
fetch_etoro.py — eToro portfolio ingestion.

## eToro API status (as of 2026)

eToro launched an official public API on 29 October 2025.
Documentation portal: https://api-portal.etoro.com/

The API provides programmatic access to:
  - Open positions (PnL, value, entry price, current price)
  - Portfolio history and trading history
  - Order execution and management
  - Social features (watchlists, posts)

### Access requirements
  - Verified eToro account
  - Developer access keys obtained from the API portal
  - Required env vars:  ETORO_PUBLIC_API_KEY  and  ETORO_USER_KEY

### Authentication
The API uses a key-pair scheme passed as HTTP headers:
  x-api-key: <ETORO_PUBLIC_API_KEY>
  x-user-key: <ETORO_USER_KEY>

### CORS note
Some eToro API endpoints enforce CORS restrictions.
Always call from a server-side environment, never from a browser.

### ToS note
Use of the official API is subject to eToro's developer Terms of Service.
Scraping the eToro web application is fragile, legally risky, and not
supported by this module.

## Fallback: CSV export
If API access is unavailable, eToro allows manual portfolio export via:
  Portfolio → Export to CSV
Use  parse_csv_export()  to produce the same raw_data dict as fetch_portfolio().
"""

import csv
import os
import logging
from src.utils import get_utc_timestamp, generate_request_id, get_retry_session, write_json

logger = logging.getLogger(__name__)

# Official eToro public API — verify path at https://api-portal.etoro.com/
# Launched October 2025; endpoint path may change — check the portal if you
# receive 404 errors.
ETORO_API_URL = "https://public-api.etoro.com/api/v1/trading/info/portfolio"


# ---------------------------------------------------------------------------
# Primary: REST API
# ---------------------------------------------------------------------------

def fetch_portfolio(out_dir: str = "out") -> dict:
    """
    Fetch the eToro portfolio via the official public REST API.

    Requires env vars:
      ETORO_PUBLIC_API_KEY   — developer API key from api-portal.etoro.com
      ETORO_USER_KEY         — per-user key from api-portal.etoro.com

    Returns the parsed JSON response dict and writes the raw payload to out_dir.

    Raises ValueError if credentials are missing.
    Raises requests.HTTPError if the API returns a non-2xx status.
    """
    api_key = os.environ.get("ETORO_PUBLIC_API_KEY")
    user_key = os.environ.get("ETORO_USER_KEY")

    if not api_key or not user_key:
        raise ValueError(
            "ETORO_PUBLIC_API_KEY and ETORO_USER_KEY env vars must be set. "
            "Obtain developer keys at https://api-portal.etoro.com/ "
            "(requires a verified eToro account)."
        )

    headers = {
        "x-request-id": generate_request_id(),
        "x-api-key": api_key,
        "x-user-key": user_key,
        "Content-Type": "application/json",
    }

    logger.info("Fetching eToro portfolio from official public API...")
    session = get_retry_session()
    response = session.get(ETORO_API_URL, headers=headers)
    response.raise_for_status()

    data = response.json()

    timestamp = get_utc_timestamp()
    filepath = os.path.join(out_dir, f"raw_{timestamp}.json")
    write_json(data, filepath)
    logger.info(f"Raw API response saved to {filepath}")

    return data


# ---------------------------------------------------------------------------
# Fallback: CSV export parser
# ---------------------------------------------------------------------------

def parse_csv_export(csv_path: str) -> dict:
    """
    Parse a manual eToro portfolio CSV export into the same raw_data dict
    format expected by normalize_portfolio().

    How to export from eToro:
      Portfolio page → kebab menu → Export to CSV

    Typical CSV columns:
      Position ID, Action, Amount ($), Units, Open Rate, Open Date,
      Leverage, Spread, Profit ($), Value ($), Type, ISIN, Notes

    Returns a dict mirroring the clientPortfolio structure so normalize.py
    can handle it without modification.

    Limitation: the CSV captures a point-in-time snapshot; it does not
    provide a live current price feed.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"eToro CSV export not found at: {csv_path}")

    def _float(row: dict, *keys, default: float = 0.0) -> float:
        for key in keys:
            raw = row.get(key, "")
            if raw:
                cleaned = str(raw).replace("$", "").replace(",", "").strip()
                try:
                    return float(cleaned)
                except (ValueError, TypeError):
                    continue
        return default

    positions = []
    total_value = 0.0

    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            action = (row.get("Action") or "").strip()
            # Skip header-like or summary rows
            if not action or action.lower() in ("", "total", "summary", "action"):
                continue

            amount = _float(row, "Amount ($)", "Amount", default=0.0)
            units = _float(row, "Units", default=0.0)
            open_rate = _float(row, "Open Rate", default=0.0)
            profit = _float(row, "Profit ($)", "Profit", default=0.0)
            # Value ($) = current market value; fall back to amount + profit
            value = _float(row, "Value ($)", "Value", default=amount + profit)
            notes = (row.get("Notes") or "").strip()

            # Ticker: Notes often contains the instrument symbol on eToro.
            # Fall back to Action (the instrument name).
            ticker = notes if notes else action

            total_value += value
            positions.append({
                # _csv_ticker is consumed by normalize.py's CSV path
                "_csv_ticker": ticker,
                "instrumentID": None,
                "amount": value,       # use current value as the weight denominator
                "units": units,
                "openRate": open_rate,
                "profit": profit,
                "isin": (row.get("ISIN") or row.get("Isin") or "").strip(),
            })

    logger.info(
        f"Parsed eToro CSV export: {len(positions)} positions, "
        f"total value ${total_value:,.2f}"
    )

    # credit (cash) is not reported in the CSV; default to 0
    return {
        "clientPortfolio": {
            "positions": positions,
            "credit": 0.0,
            "_source": "csv_export",
        }
    }
