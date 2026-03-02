import logging
import yfinance as yf
import pandas as pd

logger = logging.getLogger(__name__)

def fetch_yahoo_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """
    Fetches historical data for a given Yahoo Finance ticker.
    Period can be '1y', 'ytd', 'max', '1mo', etc.
    Returns a pandas DataFrame.
    """
    try:
        logger.info(f"Fetching Yahoo Finance history for {ticker} (period: {period})...")
        t = yf.Ticker(ticker)
        df = t.history(period=period)
        if df.empty:
            raise ValueError(f"No data returned for ticker {ticker}")
            
        return df
    except Exception as e:
        logger.error(f"Error fetching Yahoo Finance data for {ticker}: {e}")
        raise

def get_latest_price(ticker: str) -> float:
    """
    Utility to just get the last closing price.
    """
    df = fetch_yahoo_history(ticker, period="1mo")
    return float(df['Close'].iloc[-1])
