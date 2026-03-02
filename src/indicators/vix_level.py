import logging
from src.collectors.market_prices_collector import get_latest_price

logger = logging.getLogger(__name__)

def evaluate_vix_level() -> dict:
    """
    Evaluates the VIX level.
    """
    logger.info("Evaluating VIX Level...")
    current_vix = get_latest_price("^VIX")
    return {
        "current_vix": round(current_vix, 2)
    }
