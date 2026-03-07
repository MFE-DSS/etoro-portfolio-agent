import os
import json
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone
from jsonschema import validate, ValidationError
from src.decision_engine.prompts import SYSTEM_PROMPT, build_user_prompt, REPAIR_PROMPT

logger = logging.getLogger(__name__)

def build_fallback_decisions(snapshot: Dict[str, Any], market_state: Dict[str, Any], portfolio_state: Dict[str, Any], message: str) -> Dict[str, Any]:
    """Generates a safe determinist fallback decision payload."""
    positions = portfolio_state.get("positions", [])
    actions = []
    
    for i, p in enumerate(positions[:5]):
        actions.append({
            "ticker": p["ticker"],
            "action": "HOLD",
            "priority": i + 1,
            "rationale": "Fallback mode: Safe HOLD due to engine failure.",
            "max_change_pct": 0.0
        })
        
    cash = snapshot.get("cash_pct", 0.0)
    
    flags = portfolio_state.get("risk_overlay", {}).get("flags", [])
    overweights = [p for p in positions if p.get("weight_pct", 0.0) > 0.10]
    ow_list = [{"ticker": p["ticker"], "weight_pct": p.get("weight_pct", 0.0), "reason": "Overweight heuristic (>10%)"} for p in overweights]
    
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "regime_summary": {
            "risk_score": market_state.get("risk_score", 50),
            "color": market_state.get("color", "orange"),
            "key_risks": ["Engine degradation fallback active."],
            "key_supports": ["Fallback initialized safely."]
        },
        "portfolio_diagnosis": {
            "cash_pct": cash,
            "concentration_flags": ["Fallback mode active. Detailed concentration skipped."],
            "correlation_flags": [],
            "overweights": ow_list,
            "missing_metadata": [f for f in flags if f == "MISSING_ASSET_METADATA"]
        },
        "actions": actions,
        "dca_plan_2m": [
            {
                "week": 1,
                "allocation_pct_of_cash": 0.0,
                "targets": [],
                "conditions": ["PAUSE: Fallback engine active."]
            }
        ],
        "alerts": [
            {
                "name": "Engine Fallback",
                "condition": "LLM returned invalid or empty JSON.",
                "meaning": message,
                "response": "Ensure Gemini API is healthy and prompt boundaries are strict."
            }
        ]
    }

def clean_llm_json(raw_text: str) -> str:
    """Removes common markdown formatting from LLM output."""
    raw_text = raw_text.strip()
    if raw_text.startswith("```json"):
        raw_text = raw_text[7:]
    elif raw_text.startswith("```"):
        raw_text = raw_text[3:]
    if raw_text.endswith("```"):
        raw_text = raw_text[:-3]
    return raw_text.strip()

def strip_invalid_tickers(decisions: Dict[str, Any], valid_tickers: List[str]) -> Dict[str, Any]:
    """Ensures no hallucinated tickers exist in the payload."""
    valid_set = set(valid_tickers)
    
    # Clean Actions
    clean_actions = []
    for action in decisions.get("actions", []):
        if action.get("ticker", "UNKNOWN") in valid_set:
            clean_actions.append(action)
    decisions["actions"] = clean_actions
    
    # Clean DCA
    for week in decisions.get("dca_plan_2m", []):
        clean_targets = []
        for target in week.get("targets", []):
            if target.get("ticker", "UNKNOWN") in valid_set:
                clean_targets.append(target)
        week["targets"] = clean_targets
        
    return decisions

def generate_decisions(snapshot: Dict[str, Any], market_state: Dict[str, Any], portfolio_state: Dict[str, Any], valid_tickers: List[str]) -> Dict[str, Any]:
    """
    Main entry point for V4 Decision Engine.
    Calls LLM, validates, and handles fallbacks.
    """
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        logger.error("GEMINI_API_KEY not found. Triggering fallback.")
        return build_fallback_decisions(snapshot, market_state, portfolio_state, "API Key missing.")
        
    from google import genai
    client = genai.Client(api_key=api_key)
    
    # Load schema for validation
    schema_path = os.path.join(os.path.dirname(__file__), "..", "..", "schemas", "decisions.schema.json")
    try:
        with open(schema_path, "r") as f:
            schema = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load decisions schema: {e}")
        return build_fallback_decisions(snapshot, market_state, portfolio_state, "Schema file missing.")

    prompt = build_user_prompt(snapshot, market_state, portfolio_state, valid_tickers, json.dumps(schema, indent=2))
    
    chat_config = {"system_instruction": SYSTEM_PROMPT}

    # Attempt 1
    try:
        chat = client.chats.create(model="gemini-2.5-flash", config=chat_config)
        response = chat.send_message(prompt)
        raw_json = clean_llm_json(response.text)
        decisions = json.loads(raw_json)
        decisions = strip_invalid_tickers(decisions, valid_tickers)
        validate(instance=decisions, schema=schema)
        return decisions
    except (json.JSONDecodeError, ValidationError) as e:
        logger.warning(f"Attempt 1 failed schema validation or decoding: {e}. Retrying with repair prompt...")
    except Exception as e:
        logger.error(f"Attempt 1 failed with unexpected error: {e}")
        return build_fallback_decisions(snapshot, market_state, portfolio_state, f"Unexpected error: {e}")
        
    # Attempt 2 (Repair)
    try:
        response = chat.send_message(REPAIR_PROMPT)
        raw_json = clean_llm_json(response.text)
        decisions = json.loads(raw_json)
        decisions = strip_invalid_tickers(decisions, valid_tickers)
        validate(instance=decisions, schema=schema)
        return decisions
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Attempt 2 failed validation: {e}. Triggering fallback.")
        return build_fallback_decisions(snapshot, market_state, portfolio_state, f"Schema validation failed after repair: {e}")
    except Exception as e:
        logger.error(f"Attempt 2 failed with unexpected error: {e}")
        return build_fallback_decisions(snapshot, market_state, portfolio_state, f"Unexpected error on repair: {e}")
