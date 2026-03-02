import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_credit_stress(data: Dict[str, SeriesData]) -> dict:
    """Evaluates High Yield Spread level and 1mo change if available."""
    hy = data.get('hy_spread')
    
    level = None
    change_1m = None
    
    if hy and hy.data:
        df = pd.DataFrame([{'date': p.date, 'value': p.value} for p in hy.data])
        level = float(df['value'].iloc[-1])
        
        if len(df) >= 21: # roughly 1 month info
            change_1m = level - float(df['value'].iloc[-21])
            
    return {
        'hy_spread_level': level,
        'hy_spread_change_1m': change_1m
    }
