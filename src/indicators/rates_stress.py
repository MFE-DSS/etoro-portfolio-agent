import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_rates_stress(data: Dict[str, SeriesData]) -> dict:
    """Evaluates 10Y Yield Level and Yield Curve (10y-2y)."""
    us10y = data.get('us10y')
    curve = data.get('yield_curve')
    
    us10y_level = None
    curve_level = None
    
    if us10y and us10y.data:
        us10y_level = us10y.latest
        
    if curve and curve.data:
        curve_level = curve.latest
        
    return {
        'us10y_level': us10y_level,
        'yield_curve_10y_2y': curve_level
    }
