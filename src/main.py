import sys
import logging
from src.fetch_etoro import fetch_portfolio
from src.normalize import normalize_portfolio
from src.analyze_llm import analyze_portfolio

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting eToro Portfolio Agent pipeline...")
    
    try:
        # Step 0: Market Regime Model (V2)
        logger.info("=== STEP 0: Market Regime Model ===")
        from src.scoring.regime_model import evaluate_regimes_and_scores
        from src.collectors.fred_collector import fetch_all_fred
        from src.collectors.market_prices_collector import fetch_all_market_prices
        from datetime import datetime, timezone
        import json
        import os
        from jsonschema import validate
        
        logger.info("Fetching macroeconomic data from FRED...")
        fred_data = fetch_all_fred()
        
        logger.info("Fetching market prices from YF...")
        market_data = fetch_all_market_prices()
        
        # Merge data collections
        all_data = {**fred_data, **market_data}
        
        market_state = evaluate_regimes_and_scores(all_data)
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
        
        # Step 3: Portfolio Overlay (V3)
        logger.info("=== STEP 3: Portfolio Overlay (V3) ===")
        from src.portfolio.portfolio_overlay import build_portfolio_state
        portfolio_state = build_portfolio_state(snapshot, market_state)
        
        with open("schemas/portfolio_state.schema.json", "r") as f:
            portfolio_schema = json.load(f)
        validate(instance=portfolio_state, schema=portfolio_schema)
        
        out_file_port = f"out/portfolio_state_{ts_str}.json"
        with open(out_file_port, "w") as f:
            json.dump(portfolio_state, f, indent=2)
        logger.info(f"Portfolio state saved to {out_file_port}")
        
        # Step 4: Decision Engine (V4)
        logger.info("=== STEP 4: Decision Engine (V4) ===")
        from src.decision_engine.engine import generate_decisions
        import yaml
        
        # Load valid tickers from config and snapshot
        try:
            with open("config/assets.yml", "r") as f:
                assets_config = yaml.safe_load(f) or {}
            valid_tickers = list(assets_config.keys())
        except:
            valid_tickers = []
            
        for pos in snapshot.get("positions", []):
            if pos.get("ticker") not in valid_tickers:
                valid_tickers.append(pos.get("ticker"))

        decisions = generate_decisions(snapshot, market_state, portfolio_state, valid_tickers)
        
        out_file_decisions = f"out/decisions_{ts_str}.json"
        with open(out_file_decisions, "w") as f:
            json.dump(decisions, f, indent=2)
        logger.info(f"Decisions saved to {out_file_decisions}")
        
        # Stop after V4
        logger.info("Stopping after V4. Next up: V5 Publishing (optional).")
        
        logger.info("Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
