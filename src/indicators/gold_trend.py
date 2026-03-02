import logging
from src.collectors.market_prices_collector import fetch_yahoo_history

logger = logging.getLogger(__name__)

def evaluate_gold_trend() -> dict:
    """
    Evaluates the Gold trend comparing current price to 50d and 200d MA.
    """
    logger.info("Evaluating Gold Trend...")
    df = fetch_yahoo_history("GC=F", period="1y")
    
    # Calculate MAs
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()
    
    latest = df.iloc[-1]
    current_price = float(latest['Close'])
    ma50 = float(latest['MA50'])
    ma200 = float(latest['MA200'])
    
    above_ma50 = current_price > ma50
    above_ma200 = current_price > ma200
    
    return {
        "current_price": round(current_price, 2),
        "ma50": round(ma50, 2),
        "ma200": round(ma200, 2),
        "above_ma50": above_ma50,
        "above_ma200": above_ma200
    }
