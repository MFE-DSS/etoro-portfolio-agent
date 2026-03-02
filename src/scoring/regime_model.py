import logging
from typing import Dict, Any
from src.collectors.models import SeriesData
from src.indicators.trend import evaluate_trend
from src.indicators.volatility import evaluate_volatility
from src.indicators.credit_stress import evaluate_credit_stress
from src.indicators.rates_stress import evaluate_rates_stress
from src.indicators.usd_gold_stress import evaluate_usd_gold_stress
from src.indicators.inflation_pressure import evaluate_inflation_pressure
from src.indicators.growth_slowing import evaluate_growth_slowing

logger = logging.getLogger(__name__)

def evaluate_regimes_and_scores(data: Dict[str, SeriesData]) -> Dict[str, Any]:
    """Calculates all sub-scores, probabilities, and final risk score."""
    
    # Run indicators
    ind_trend = evaluate_trend(data)
    ind_vol = evaluate_volatility(data)
    ind_credit = evaluate_credit_stress(data)
    ind_rates = evaluate_rates_stress(data)
    ind_usd_gold = evaluate_usd_gold_stress(data)
    ind_inflation = evaluate_inflation_pressure(data)
    ind_growth = evaluate_growth_slowing(data)
    
    # Evaluate Sub-scores (0-100, 100 = full risk on / no stress)
    # We invert stress metrics so 100 is always "good" for risk assets.
    
    # 1. Risk / Equity Trend
    spx_ma = 0
    if ind_trend.get('spx'):
        spx_ma += 25 if ind_trend['spx']['above_ma50'] else 0
        spx_ma += 25 if ind_trend['spx']['above_ma200'] else 0
    ndx_ma = 0
    if ind_trend.get('ndx'):
        ndx_ma += 25 if ind_trend['ndx']['above_ma50'] else 0
        ndx_ma += 25 if ind_trend['ndx']['above_ma200'] else 0
    risk_score = spx_ma + ndx_ma if (ind_trend.get('spx') or ind_trend.get('ndx')) else 50
    
    # 2. Volatility (Liquidity / Stress proxy)
    vix = ind_vol.get('vix_level')
    if vix is None:
        liquidity_score = 50
    elif vix < 15: liquidity_score = 90
    elif vix < 20: liquidity_score = 70
    elif vix < 25: liquidity_score = 40
    elif vix < 30: liquidity_score = 20
    else: liquidity_score = 10
    
    # 3. Credit
    hy = ind_credit.get('hy_spread_level')
    if hy is None:
        credit_score = 50
    elif hy < 4.0: credit_score = 90
    elif hy < 5.0: credit_score = 60
    elif hy < 6.0: credit_score = 30
    else: credit_score = 10
        
    # 4. USD Stress
    dxy = ind_usd_gold.get('dxy_above_ma50')
    usd_stress_score = 20 if dxy else 80
    
    # 5. Commodities Stress (Gold acting as safe haven)
    gold = ind_usd_gold.get('gold_above_ma50')
    commodities_stress_score = 20 if gold else 80
    
    # 6. Growth
    unemp = ind_growth.get('unemployment_rising')
    growth_score = 20 if unemp else 80
    
    # 7. Inflation
    cpi = ind_inflation.get('cpi_headline_yoy')
    if cpi is None:
        inflation_score = 50
    elif cpi > 4.0: inflation_score = 20
    elif cpi > 3.0: inflation_score = 40
    else: inflation_score = 80
        
    # Compile sub-scores
    sub_scores = {
        'risk': get_score_dict(risk_score),
        'growth': get_score_dict(growth_score),
        'inflation': get_score_dict(inflation_score),
        'liquidity': get_score_dict(liquidity_score),
        'credit': get_score_dict(credit_score),
        'usd_stress': get_score_dict(usd_stress_score),
        'commodities_stress': get_score_dict(commodities_stress_score),
    }
    
    # Evaluate Probabilities (0.0 to 1.0)
    # Recession Risk: high if unemp rising + credit spread > 5
    recession_risk = 0.8 if (unemp and (hy and hy > 5.0)) else 0.2
    
    # Policy Shock: high if rates rising rapidly or inflation > 4
    policy_shock_risk = 0.7 if (cpi and cpi > 4.0) else 0.1
    
    # Inflation Resurgence
    inflation_resurgence_risk = 0.6 if (cpi and cpi > 3.5 and ind_usd_gold.get('gold_above_ma50')) else 0.2
    
    # Liquidity Stress
    liquidity_stress_risk = 0.8 if (vix and vix > 25 and dxy) else 0.2
    
    probabilities = {
        'recession_risk': recession_risk,
        'policy_shock_risk': policy_shock_risk,
        'inflation_resurgence_risk': inflation_resurgence_risk,
        'liquidity_stress_risk': liquidity_stress_risk
    }
    
    # Final Aggregation
    final_score = int((risk_score * 0.4) + (liquidity_score * 0.2) + (credit_score * 0.2) + (growth_score * 0.2))
    final_score = max(0, min(100, final_score))
    
    state = {
        "risk_score": final_score,
        "color": get_color(final_score),
        "sub_scores": sub_scores,
        "regime_probabilities": probabilities,
        "indicators": {
            "trend": ind_trend,
            "volatility": ind_vol,
            "credit": ind_credit,
            "rates": ind_rates,
            "usd_gold": ind_usd_gold,
            "inflation": ind_inflation,
            "growth": ind_growth
        }
    }
    
    return state
    
def get_color(score: int) -> str:
    if score >= 70: return "green"
    elif score >= 40: return "orange"
    return "red"
    
def get_score_dict(score: int) -> dict:
    return {
        "score": score,
        "color": get_color(score)
    }
