import logging
from src.collectors.fred_collector import fetch_fred_series

logger = logging.getLogger(__name__)

def evaluate_us10y_level() -> dict:
    """
    Evaluates US 10 Year Yield.
    """
    logger.info("Evaluating US 10Y Level...")
    yield_val = fetch_fred_series("DGS10")
    return {
        "current_yield": round(yield_val, 2)
    }
