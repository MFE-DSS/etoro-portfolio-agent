import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_usd_gold_stress(data: Dict[str, SeriesData]) -> dict:
    """Evaluates DXY and Gold."""
    dxy = data.get('dxy')
    gold = data.get('gold')
    
    dxy_level = None
    dxy_above_ma50 = False
    
    if dxy and len(dxy.data) >= 50:
        df = pd.DataFrame([{'v': p.value} for p in dxy.data])
        df['ma50'] = df['v'].rolling(50).mean()
        latest = df.iloc[-1]
        dxy_level = latest['v']
        dxy_above_ma50 = bool(latest['v'] > latest['ma50'])
    elif dxy and dxy.data:
        dxy_level = dxy.latest
        
    gold_level = None
    gold_above_ma50 = False
    if gold and len(gold.data) >= 50:
        df = pd.DataFrame([{'v': p.value} for p in gold.data])
        df['ma50'] = df['v'].rolling(50).mean()
        latest = df.iloc[-1]
        gold_level = latest['v']
        gold_above_ma50 = bool(latest['v'] > latest['ma50'])
    elif gold and gold.data:
        gold_level = gold.latest

    return {
        'dxy_level': dxy_level,
        'dxy_above_ma50': dxy_above_ma50,
        'gold_level': gold_level,
        'gold_above_ma50': gold_above_ma50
    }
