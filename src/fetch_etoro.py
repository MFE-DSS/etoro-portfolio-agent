import os
import logging
from src.utils import get_utc_timestamp, generate_request_id, get_retry_session, write_json

logger = logging.getLogger(__name__)

ETORO_API_URL = "https://public-api.etoro.com/api/v1/trading/info/portfolio"

def fetch_portfolio(out_dir: str = "out") -> dict:
    """
    Fetches the eToro portfolio using public API.
    Requires ETORO_PUBLIC_API_KEY and ETORO_USER_KEY env variables.
    Saves raw response to out_dir and returns the parsed JSON dict.
    """
    api_key = os.environ.get("ETORO_PUBLIC_API_KEY")
    user_key = os.environ.get("ETORO_USER_KEY")

    if not api_key or not user_key:
        raise ValueError(
            "Environment variables ETORO_PUBLIC_API_KEY and ETORO_USER_KEY must be set."
        )

    headers = {
        "x-request-id": generate_request_id(),
        "x-api-key": api_key,
        "x-user-key": user_key,
        "Content-Type": "application/json"
    }

    logger.info("Fetching eToro portfolio from public API...")
    session = get_retry_session()
    
    response = session.get(ETORO_API_URL, headers=headers)
    response.raise_for_status()

    data = response.json()
    
    timestamp = get_utc_timestamp()
    filepath = os.path.join(out_dir, f"raw_{timestamp}.json")
    write_json(data, filepath)
    
    return data
