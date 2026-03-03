import sys
import logging
import json
import os
from datetime import datetime, timezone
from jsonschema import validate

# Remove basicConfig if it was there, we'll set it up dynamically
logger = logging.getLogger(__name__)

def setup_logging(ts_str: str):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)
    
    # JSONL handler
    os.makedirs("out", exist_ok=True)
    fh = logging.FileHandler(f"out/logs_{ts_str}.jsonl")
    fh.setLevel(logging.INFO)
    class JsonFormatter(logging.Formatter):
        def format(self, record):
            log_record = {
                "timestamp": self.formatTime(record, self.datefmt),
                "name": record.name,
                "level": record.levelname,
                "message": record.getMessage()
            }
            return json.dumps(log_record)
    fh.setFormatter(JsonFormatter())
    root_logger.addHandler(fh)

def main():
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_str = ts_iso.replace(":", "").replace("-", "")[:15] # YYYYMMDD_HHMMSS
    
    setup_logging(ts_str)
    
    logger.info("Starting eToro Portfolio Agent pipeline...")
    
    try:
        # Step 0: Market Regime Model (V2)
        logger.info("=== STEP 0: Market Regime Model ===")
        from src.scoring.regime_model import evaluate_regimes_and_scores
        from src.collectors.fred_collector import fetch_all_fred
        from src.collectors.market_prices_collector import fetch_all_market_prices
        
        logger.info("Fetching macroeconomic data from FRED...")
        fred_data = fetch_all_fred()
        
        logger.info("Fetching market prices from YF...")
        market_data = fetch_all_market_prices()
        
        all_data = {**fred_data, **market_data}
        
        market_state = evaluate_regimes_and_scores(all_data)
        market_state['timestamp'] = ts_iso
        
        with open("schemas/market_state.schema.json", "r") as f:
            schema = json.load(f)
        validate(instance=market_state, schema=schema)
        
        out_file = f"out/market_state_{ts_str}.json"
        with open(out_file, "w") as f:
            json.dump(market_state, f, indent=2)
        logger.info(f"Market state saved to {out_file}")

        # Step 1: Fetch raw data
        logger.info("=== STEP 1: Fetch ===")
        from src.fetch_etoro import fetch_portfolio
        if not os.environ.get("ETORO_PUBLIC_API_KEY"):
            logger.info("ETORO_PUBLIC_API_KEY missing. Running in DRY MODE with fixture.")
            with open("tests/fixtures/snapshot.json", "r") as f:
                raw_data = json.load(f)
        else:
            raw_data = fetch_portfolio()
        
        # Step 2: Normalize data
        logger.info("=== STEP 2: Normalize ===")
        from src.normalize import normalize_portfolio
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
        
        # Step 5: Monitoring, Storage & Publishing (V5)
        logger.info("=== STEP 5: Monitoring & Storage (V5) ===")
        from src.monitoring.health_score import compute_health_score
        from src.monitoring.alerts import evaluate_alerts
        from src.monitoring.storage import extract_history_row, append_to_history, create_run_bundle
        from src.publish.publish import zip_run_bundle, generate_markdown_report, optional_google_drive_upload
        
        summary = compute_health_score(market_state, portfolio_state, decisions)
        summary["timestamp"] = ts_iso
        
        with open("schemas/summary.schema.json", "r") as f:
            summary_schema = json.load(f)
        validate(instance=summary, schema=summary_schema)
        
        out_file_summary = f"out/summary_{ts_str}.json"
        with open(out_file_summary, "w") as f:
            json.dump(summary, f, indent=2)
            
        alerts = evaluate_alerts(market_state, portfolio_state)
        with open("schemas/alerts.schema.json", "r") as f:
            alerts_schema = json.load(f)
        validate(instance=alerts, schema=alerts_schema)
        
        out_file_alerts = f"out/alerts_{ts_str}.json"
        with open(out_file_alerts, "w") as f:
            json.dump(alerts, f, indent=2)
            
        logger.info("Appending to history...")
        history_row = extract_history_row(ts_iso, market_state, portfolio_state, decisions, summary)
        append_to_history(history_row)
        
        logger.info("Creating run bundle and publishing artifacts...")
        bundle_dir = create_run_bundle(ts_str, ts_iso, snapshot, market_state, portfolio_state, decisions, summary, alerts)
        zip_path = zip_run_bundle(bundle_dir)
        report_path = generate_markdown_report(ts_str, summary, alerts)
        optional_google_drive_upload(zip_path)
        
        # Step 6: Webhook Broadcasting (V6)
        logger.info("=== STEP 6: Webhook Broadcasting (V6) ===")
        from src.publish.notifier import send_webhook_notification
        send_webhook_notification(report_path, ts_str)
        
        logger.info("Pipeline completed successfully.")
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    main()
