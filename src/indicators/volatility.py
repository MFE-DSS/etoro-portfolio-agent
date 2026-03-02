from typing import Dict
from src.collectors.models import SeriesData

def evaluate_volatility(data: Dict[str, SeriesData]) -> dict:
    """Evaluates VIX or vol proxy."""
    vix = data.get('vix')
    
    current_vix = None
    if vix and vix.data:
        current_vix = vix.latest
        
    return {
        'vix_level': current_vix
    }
