import sys
import logging
from src.fetch_etoro import fetch_portfolio
from src.normalize import normalize_portfolio
from src.analyze_llm import analyze_portfolio

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting eToro Portfolio Agent pipeline...")
    
    try:
        # Step 0: Market Regime Model
        logger.info("=== STEP 0: Market Regime Model ===")
        from src.scoring.risk_on_score import calculate_risk_score
        from datetime import datetime, timezone
        import json
        import os
        from jsonschema import validate
        
        market_state = calculate_risk_score()
        market_state['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        with open("schemas/market_state.schema.json", "r") as f:
            schema = json.load(f)
        validate(instance=market_state, schema=schema)
        
        os.makedirs("out", exist_ok=True)
        ts_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        out_file = f"out/market_state_{ts_str}.json"
        with open(out_file, "w") as f:
            json.dump(market_state, f, indent=2)
        logger.info(f"Market state saved to {out_file}")

        # Step 1: Fetch raw data
        logger.info("=== STEP 1: Fetch ===")
        raw_data = fetch_portfolio()
        
        # Step 2: Normalize data
        logger.info("=== STEP 2: Normalize ===")
        snapshot = normalize_portfolio(raw_data)
        
        # Step 3: LLM Analysis
        logger.info("=== STEP 3: Analyze ===")
        decisions = analyze_portfolio(snapshot)
        
        logger.info("Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
