import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_inflation_pressure(data: Dict[str, SeriesData]) -> dict:
    """Evaluates YoY Inflation pressure using CPI headline/core if available."""
    headline = data.get('cpi_headline')
    core = data.get('cpi_core')
    
    headline_yoy = None
    core_yoy = None
    
    # FRED CPI acts as index. YoY change = (current / 12 months ago) - 1
    # Assuming daily or monthly data over 200 rows covers a year if monthly, but daily covers < 1 yr.
    # FRED CPI is monthly, so 200 rows covers ~16 years.
    
    def get_yoy(series: SeriesData):
        if not series or len(series.data) < 13:
            return None
        df = pd.DataFrame([{'date': pd.to_datetime(p.date), 'v': p.value} for p in series.data])
        df = df.set_index('date').resample('M').last() # force monthly just in case
        if len(df) < 13:
            return None
        current = df['v'].iloc[-1]
        year_ago = df['v'].iloc[-13]
        if year_ago == 0:
            return None
        return (current / year_ago - 1) * 100
        
    try:
        headline_yoy = get_yoy(headline)
        core_yoy = get_yoy(core)
    except Exception:
        pass

    return {
        'cpi_headline_yoy': headline_yoy,
        'cpi_core_yoy': core_yoy
    }
