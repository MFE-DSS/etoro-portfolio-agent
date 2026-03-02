import sys
import logging
from src.fetch_etoro import fetch_portfolio
from src.normalize import normalize_portfolio
from src.analyze_llm import analyze_portfolio

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting eToro Portfolio Agent pipeline...")
    
    try:
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
