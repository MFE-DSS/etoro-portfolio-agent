import logging
from src.indicators.spx_trend import evaluate_spx_trend
from src.indicators.ndx_trend import evaluate_ndx_trend
from src.indicators.vix_level import evaluate_vix_level
from src.indicators.hy_oas_spread import evaluate_hy_oas_spread
from src.indicators.us10y_level import evaluate_us10y_level
from src.indicators.dxy_level import evaluate_dxy_level
from src.indicators.gold_trend import evaluate_gold_trend

logger = logging.getLogger(__name__)

def calculate_risk_score() -> dict:
    """
    Calls all indicators, aggregates them, and computes a risk score.
    Returns the partial market state dict (without timestamp, added elsewhere).
    """
    logger.info("Calculating Risk Score...")
    
    # Gather indicators
    spx = evaluate_spx_trend()
    ndx = evaluate_ndx_trend()
    vix = evaluate_vix_level()
    hy_oas = evaluate_hy_oas_spread()
    us10y = evaluate_us10y_level()
    dxy = evaluate_dxy_level()
    gold = evaluate_gold_trend()

    # Simple deterministic rule-based score (max 100)
    score = 50
    
    # Equities trend
    if spx['above_ma50']: score += 5
    if spx['above_ma200']: score += 10
    if ndx['above_ma50']: score += 5
    if ndx['above_ma200']: score += 10
    
    # Volatility
    if vix['current_vix'] < 15: score += 10
    elif vix['current_vix'] < 20: score += 5
    elif vix['current_vix'] > 25: score -= 15
    elif vix['current_vix'] > 30: score -= 25

    # Credit Spreads
    if hy_oas['current_spread'] < 4: score += 10
    elif hy_oas['current_spread'] > 5: score -= 15
    elif hy_oas['current_spread'] > 6: score -= 25

    if gold['above_ma50'] and spx['above_ma50']:
        score += 5
        
    # Cap score
    score = max(0, min(100, score))

    if score >= 70:
        color = "green"
    elif score >= 40:
        color = "orange"
    else:
        color = "red"

    state = {
        "indicators": {
            "spx": spx,
            "ndx": ndx,
            "vix": vix,
            "hy_oas": hy_oas,
            "us10y": us10y,
            "dxy": dxy,
            "gold": gold
        },
        "risk_score": score,
        "color": color
    }
    logger.info(f"Risk Score evaluated to {score} ({color})")
    
    return state
