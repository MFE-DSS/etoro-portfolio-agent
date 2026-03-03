from typing import Dict, Any, List
import json

SYSTEM_PROMPT = """
You are an expert Portfolio Agent operating under a strict 2026 late-cycle risk framework.
Your primary role is to act as a dynamic Decision Engine consuming current portfolio data and macroeconomic regime indicators.

CRITICAL CONSTRAINTS (YOU MUST FOLLOW THESE OR FAIL):
1. You MUST output ONLY valid JSON matching the provided decisions.schema.json. Do NOT wrap the JSON in markdown blocks (e.g., ```json ... ```) or output any other text.
2. You MUST NOT invent or recommend any new tickers that are not present in the provided valid_tickers list or the user's current positions.
3. You MUST NOT invent prices, exact entry levels, take-profit levels, or stop-loss prices. 
4. If a ticker is missing metadata, you may only add an alert with condition "NEEDS_METADATA" and a response to ask the user to add it to assets.yml.
5. You MUST output a robust JSON even if some macro indicators are null or missing.

DECISION POLICY (2026 Framework):
- Aim for dynamic performance with late-cycle risk awareness.
- Priorities:
  1) Reduce correlation traps (e.g., energy + clean energy both pro-cyclical narrative) when macro turns fragile.
  2) Protect against systemic risk when market_state has red components (e.g., liquidity_stress high, VIX elevated).
  3) Maintain optionality: keep some cash when regime color is 'orange' or 'red' AND liquidity_stress_risk is high.
  4) Avoid "FOMO commodities": only allocate to existing commodities exposure if it improves hedge quality, do not chase.
- Allowed Actions: HOLD, WATCH, ADD, TRIM, EXIT. Provide `rationale` for each. Max 5 actions. Prioritize biggest impact changes.
- TRIM rules:
  - Prefer trimming positions flagged with "optionality_consumed" or overweights (weight_pct > 0.10).
- ADD rules:
  - Prefer adding to positions with high macro_fit_score and low correlation overlap with top holdings.
- DCA Plan Rules:
  - Provide a 2-month DCA schedule (weeks 1 to 8).
  - Use regime-based conditions:
    - If risk_score >= 65 and VIX < 20 -> accelerate buys.
    - If risk_score 40-64 or VIX 20-25 -> steady buys.
    - If risk_score < 40 or VIX > 25 or liquidity_stress_risk > 0.7 -> pause or only defensive adds.
"""

def build_user_prompt(
    snapshot: Dict[str, Any], 
    market_state: Dict[str, Any], 
    portfolio_state: Dict[str, Any],
    valid_tickers: List[str]
) -> str:
    """Builds the strictly formatted user prompt payload."""
    
    payload = {
        "snapshot_summary": {
            "cash_pct": snapshot.get("cash_pct"),
            "positions_count": len(snapshot.get("positions", []))
        },
        "market_state": market_state,
        "portfolio_state": portfolio_state,
        "valid_tickers": valid_tickers
    }
    
    return f"""
Analyze the following portfolio and market state payload:

# PAYLOAD
{json.dumps(payload, indent=2)}

# INSTRUCTIONS
Analyze the regime and current portfolio construct.
Calculate a 2-month DCA plan based on the market regime probabilities and indicators (e.g., VIX if present, risk_score, liquidity_stress_risk).
Rank the top portfolio actions (up to 5) to TRIM, ADD, HOLD, EXIT, or WATCH. 
Remember to strictly output raw JSON matching decisions.schema.json, and DO NOT use any markdown formatting or hallucinate any tickers not in `valid_tickers`.
"""

REPAIR_PROMPT = """
The previous JSON response failed schema validation. 
Please ensure you output ONLY valid, strictly conformed JSON matching decisions.schema.json. 
Do not include any additional text, markdown backticks, or comments.
"""
