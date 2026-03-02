import logging
from datetime import datetime, timedelta
import pandas as pd

logger = logging.getLogger(__name__)

def fetch_fred_series(series_id: str, days_back: int = 30) -> float:
    """
    Fetches the latest available value for a given FRED series ID.
    Returns the latest float value.
    """
    
    try:
        logger.info(f"Fetching FRED data for {series_id}...")
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        df = pd.read_csv(url)
        
        if df.empty:
            raise ValueError(f"No data returned for FRED series {series_id}")
            
        # The CSV has 'DATE' and the series_id as columns. Sometimes missing values are '.'
        df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
        df = df.dropna()
        
        if df.empty:
            raise ValueError(f"No valid numerical data returned for FRED series {series_id}")
            
        latest_value = df[series_id].iloc[-1]
        logger.info(f"Latest {series_id}: {latest_value}")
        return float(latest_value)
    except Exception as e:
        logger.error(f"Error fetching FRED series {series_id}: {e}")
        raise
