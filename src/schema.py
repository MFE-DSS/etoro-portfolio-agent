"""
Defines schemas for our application domain, especially for LLM structured outputs.
"""

LLM_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {
            "type": "string",
            "description": "High-level summary of the portfolio performance and risk."
        },
        "trades": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "ticker": {"type": "string"},
                    "action": {
                        "type": "string", 
                        "enum": ["BUY", "SELL", "HOLD"],
                        "description": "The decision for this specific asset."
                    },
                    "reasoning": {
                        "type": "string",
                        "description": "Short explanation for why this action is recommended."
                    },
                    "confidence": {
                        "type": "number",
                        "minimum": 1,
                        "maximum": 10,
                        "description": "Confidence score from 1-10 for the trade."
                    }
                },
                "required": ["ticker", "action", "reasoning", "confidence"],
                "additionalProperties": False
            }
        }
    },
    "required": ["summary", "trades"],
    "additionalProperties": False
}
