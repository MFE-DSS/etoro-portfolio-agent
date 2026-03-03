import logging
import pandas as pd
from typing import Dict, List
from src.collectors.models import DataPoint, SeriesData
from src.collectors.config_util import load_config, get_series_for_source

logger = logging.getLogger(__name__)

def fetch_all_fred(config_path: str = "config/macro_series.yml") -> Dict[str, SeriesData]:
    """
    Reads FRED: keys from config, fetches them, returns uniform data.
    """
    config = load_config(config_path)
    fred_mapping = get_series_for_source("FRED", config)
    
    result = {}
    for logical_key, series_id in fred_mapping.items():
        try:
            logger.info(f"Fetching FRED data for {logical_key} ({series_id})...")
            url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
            df = pd.read_csv(url)
            
            if df.empty:
                logger.warning(f"No data returned for FRED series {series_id}")
                continue
                
            # Date is usually 'DATE', value is usually 'series_id'
            # Convert value to numeric
            df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
            df = df.dropna()
            
            if df.empty:
                logger.warning(f"No valid data returned for FRED series {series_id}")
                continue
                
            # Take last 200 points for history (enough for MA200 if needed, though mostly for MACRO we just need last few)
            # Take last 200 points for history
            df_recent = df.tail(200)
            
            date_col = 'DATE' if 'DATE' in df.columns else 'observation_date'
            
            points = []
            for _, row in df_recent.iterrows():
                points.append(DataPoint(date=str(row[date_col]), value=float(row[series_id])))
                
            result[logical_key] = SeriesData(key=logical_key, data=points)
        except Exception as e:
            logger.error(f"Error fetching FRED series {series_id} for {logical_key}: {e}")
            
    return result

# Keeping this for backward compatibility if needed, or we can just use the new one.
def fetch_fred_series(series_id: str, days_back: int = 30) -> float:
    url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
    df = pd.read_csv(url)
    df[series_id] = pd.to_numeric(df[series_id], errors='coerce')
    df = df.dropna()
    return float(df[series_id].iloc[-1])
