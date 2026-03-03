import pandas as pd
from typing import Dict
from src.collectors.models import SeriesData

def evaluate_growth_slowing(data: Dict[str, SeriesData]) -> dict:
    """Evaluates Unemployment, Initial Claims, PMI to assess growth risk."""
    unemp = data.get('unemployment')
    claims = data.get('initial_claims')
    pmi = data.get('pmi')
    
    unemp_level = None
    unemp_rising = False
    
    if unemp and len(unemp.data) >= 4:
        df = pd.DataFrame([{'v': p.value} for p in unemp.data])
        unemp_level = float(df['v'].iloc[-1])
        # Sahm rule inspired: current vs min of last 12 mo, simplified
        if len(df) >= 12:
            min_12m = df['v'].tail(12).min()
            unemp_rising = bool((unemp_level - min_12m) >= 0.5)
        
    claims_level = None
    if claims and claims.data:
        claims_level = claims.latest
        
    pmi_level = None
    if pmi and pmi.data:
        pmi_level = pmi.latest
        
    return {
        'unemployment_level': unemp_level,
        'unemployment_rising': unemp_rising,
        'initial_claims_level': claims_level,
        'pmi_level': pmi_level
    }
