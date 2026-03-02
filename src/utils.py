import json
import logging
import os
import uuid
from datetime import datetime, timezone
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Setup highly structured, JSON-like logging format if desired,
# but for now we'll stick to a clean, timestamp-prefixed plain text format
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s - %(message)s'
)
logger = logging.getLogger(__name__)

def get_utc_timestamp() -> str:
    """Returns current UTC time in YYYYMMDD_HHMMSS format."""
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")

def generate_request_id() -> str:
    """Generates a UUID for request tracking."""
    return str(uuid.uuid4())

def write_json(data: dict, filepath: str) -> None:
    """Safely writes a dictionary to a JSON file."""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Wrote data to {filepath}")

def get_retry_session(
    retries: int = 3, 
    backoff_factor: float = 0.3, 
    status_forcelist: tuple = (429, 500, 502, 503, 504)
) -> requests.Session:
    """Returns a requests.Session with resilient retry logic."""
    session = requests.Session()
    retry = Retry(
        total=retries,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount('http://', adapter)
    session.mount('https://', adapter)
    return session
