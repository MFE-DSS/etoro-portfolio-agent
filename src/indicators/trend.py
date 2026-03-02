import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_trend(data: Dict[str, SeriesData]) -> dict:
    """Evaluates the SPX/NDX price trend vs MA50/MA200."""
    result = {}
    
    for key in ['spx', 'ndx']:
        if key in data and len(data[key].data) >= 50:
            df = pd.DataFrame([{'value': p.value} for p in data[key].data])
            df['ma50'] = df['value'].rolling(50).mean()
            df['ma200'] = df['value'].rolling(200).mean()
            
            latest = df.iloc[-1]
            current = latest['value']
            ma50 = latest['ma50'] if len(df) >= 50 else current
            ma200 = latest['ma200'] if len(df) >= 200 else current
            
            result[key] = {
                'price': current,
                'above_ma50': bool(current > ma50),
                'above_ma200': bool(current > ma200),
                'ma50': float(ma50) if not pd.isna(ma50) else float(current),
                'ma200': float(ma200) if not pd.isna(ma200) else float(current)
            }
        else:
            result[key] = None
            
    return result
