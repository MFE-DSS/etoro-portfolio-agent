import logging
from src.collectors.market_prices_collector import get_latest_price

logger = logging.getLogger(__name__)

def evaluate_dxy_level() -> dict:
    """
    Evaluates DXY Level.
    """
    logger.info("Evaluating DXY Level...")
    current_dxy = get_latest_price("DX-Y.NYB")
    return {
        "current_dxy": round(current_dxy, 2)
    }
