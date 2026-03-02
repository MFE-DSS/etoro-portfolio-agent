import logging
import yfinance as yf
import pandas as pd
from typing import Dict
from src.collectors.models import DataPoint, SeriesData
from src.collectors.config_util import load_config, get_series_for_source

logger = logging.getLogger(__name__)

def fetch_all_market_prices(config_path: str = "config/macro_series.yml") -> Dict[str, SeriesData]:
    """
    Reads YF: keys from config, fetches them, returns uniform data.
    # Note: Stooq is not directly supported via yfinance, assuming YF for now based on config provided
    """
    config = load_config(config_path)
    yf_mapping = get_series_for_source("YF", config)
    stooq_mapping = get_series_for_source("STOOQ", config)
    
    result = {}
    
    # Process YF
    for logical_key, ticker in yf_mapping.items():
        try:
            logger.info(f"Fetching YF data for {logical_key} ({ticker})...")
            t = yf.Ticker(ticker)
            df = t.history(period="1y")
            
            if df.empty:
                logger.warning(f"No data returned for ticker {ticker}")
                continue
                
            points = []
            for date, row in df.iterrows():
                # We save date as string YYYY-MM-DD
                points.append(DataPoint(date=date.strftime("%Y-%m-%d"), value=float(row['Close'])))
                
            result[logical_key] = SeriesData(key=logical_key, data=points)
        except Exception as e:
            logger.error(f"Error fetching YF data for {ticker} ({logical_key}): {e}")
            
    # STOOQ (placeholder if needed eventually, e.g. using pandas-datareader stooq or explicit csv)
    for logical_key, ticker in stooq_mapping.items():
        logger.warning(f"STOOQ not yet implemented for {logical_key} ({ticker}), skipping.")
        
    return result

def get_latest_price(ticker: str) -> float:
    t = yf.Ticker(ticker)
    df = t.history(period="1mo")
    return float(df['Close'].iloc[-1])

def fetch_yahoo_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    t = yf.Ticker(ticker)
    return t.history(period=period)
