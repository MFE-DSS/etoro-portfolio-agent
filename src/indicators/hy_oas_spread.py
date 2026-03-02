import logging
from src.collectors.fred_collector import fetch_fred_series

logger = logging.getLogger(__name__)

def evaluate_hy_oas_spread() -> dict:
    """
    Evaluates High Yield OAS Spread.
    """
    logger.info("Evaluating HY OAS Spread...")
    spread = fetch_fred_series("BAMLH0A0HYM2")
    return {
        "current_spread": round(spread, 2)
    }
