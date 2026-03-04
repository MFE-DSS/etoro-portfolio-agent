"""
Adapters for loading macro data from local CSV/Parquet files and returning standard DataFrames.
Includes optional API stubs (e.g. FRED, Yahoo Finance) that are disabled by default.
"""
import pandas as pd
import logging
from datetime import datetime, date
from typing import Dict, Optional, List
import os

logger = logging.getLogger(__name__)

class DataAdapter:
    def fetch_series(self, series_name: str, start_date: str, end_date: str) -> pd.Series:
        raise NotImplementedError

class LocalFileAdapter(DataAdapter):
    """Loads standardized CSV/Parquet data from local disk."""
    
    def __init__(self, data_dir: str):
        self.data_dir = data_dir
        
    def fetch_series(self, series_name: str, start_date: str, end_date: str) -> pd.Series:
        """
        Expects a CSV file named `<series_name>.csv` in data_dir
        with columns 'date' and 'value'.
        """
        csv_path = os.path.join(self.data_dir, f"{series_name}.csv")
        parquet_path = os.path.join(self.data_dir, f"{series_name}.parquet")
        
        df = None
        if os.path.exists(parquet_path):
            df = pd.read_parquet(parquet_path)
            logger.debug(f"Loaded {series_name} from parquet: {parquet_path}")
        elif os.path.exists(csv_path):
            df = pd.read_csv(csv_path)
            logger.debug(f"Loaded {series_name} from csv: {csv_path}")
        else:
            logger.warning(f"File for series {series_name} not found in {self.data_dir}. Returning empty series.")
            return pd.Series(name=series_name, dtype=float)
            
        if 'date' not in df.columns or 'value' not in df.columns:
            logger.error(f"Data file for {series_name} must contain 'date' and 'value' columns.")
            return pd.Series(name=series_name, dtype=float)
            
        df['date'] = pd.to_datetime(df['date'])
        
        # Filter by date range
        mask = (df['date'] >= pd.to_datetime(start_date)) & (df['date'] <= pd.to_datetime(end_date))
        df = df.loc[mask].copy()
        
        df = df.sort_values('date').set_index('date')
        
        # Attempt to handle typical FRED string na values
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        return df['value'].rename(series_name)

class FredAPIAdapter(DataAdapter):
    """Optional stub for hitting FRED API. Needs API key and internet."""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("FRED_API_KEY")
        
    def fetch_series(self, series_name: str, start_date: str, end_date: str) -> pd.Series:
        if not self.api_key:
            logger.warning(f"FRED_API_KEY missing. Cannot fetch {series_name}.")
            return pd.Series(name=series_name, dtype=float)
            
        import requests
        url = "https://api.stlouisfed.org/fred/series/observations"
        params = {
            "series_id": series_name,
            "api_key": self.api_key,
            "file_type": "json",
            "observation_start": start_date,
            "observation_end": end_date
        }
        resp = requests.get(url, params=params)
        if resp.status_code != 200:
            logger.error(f"FRED API error for {series_name}: {resp.status_code}")
            return pd.Series(name=series_name, dtype=float)
            
        data = resp.json()
        obs = data.get("observations", [])
        if not obs:
            return pd.Series(name=series_name, dtype=float)
            
        df = pd.DataFrame(obs)
        df['date'] = pd.to_datetime(df['date'])
        df['value'] = pd.to_numeric(df['value'], errors='coerce')
        return df.set_index('date')['value'].rename(series_name)

class PolygonAPIAdapter(DataAdapter):
    """Optional stub for hitting Polygon for daily equity index close. Disabled by default."""
    def __init__(self, api_key: str = None):
        self.api_key = api_key or os.environ.get("POLYGON_API_KEY")
        
    def fetch_series(self, series_name: str, start_date: str, end_date: str) -> pd.Series:
        # Impl stub...
        logger.warning("PolygonAPIAdapter not implemented. Use LocalFileAdapter.")
        return pd.Series(name=series_name, dtype=float)

def get_adapter(source_type: str, data_dir: str = "data/") -> DataAdapter:
    if source_type in ("fred", "polygon") and os.environ.get("USE_API_ADAPTERS", "false").lower() == "true":
        if source_type == "fred":
            return FredAPIAdapter()
        elif source_type == "polygon":
            return PolygonAPIAdapter()
            
    # Default to local
    return LocalFileAdapter(data_dir=data_dir)
