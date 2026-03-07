import sys
import logging
import json
import os
from datetime import datetime, timezone
from jsonschema import validate

logger = logging.getLogger(__name__)


def setup_logging(ts_str: str):
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)

    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    ch.setFormatter(formatter)
    root_logger.addHandler(ch)

    os.makedirs("out", exist_ok=True)
    fh = logging.FileHandler(f"out/logs_{ts_str}.jsonl")
    fh.setLevel(logging.INFO)

    class JsonFormatter(logging.Formatter):
        def format(self, record):
            return json.dumps({
                "timestamp": self.formatTime(record, self.datefmt),
                "name": record.name,
                "level": record.levelname,
                "message": record.getMessage(),
            })

    fh.setFormatter(JsonFormatter())
    root_logger.addHandler(fh)


def _derive_core_regime_from_market_state(market_state: dict, ts_iso: str) -> dict:
    """
    Derive a simplified core_regime dict from an already-computed market_state.

    This bridges the gap when the standalone V1 CoreMacroRegimeEngine has not
    been run.  The result is structurally identical to what the V1 engine
    produces, so the all_weather_alignment pipeline can consume it directly.

    Derived results carry  _derived_from_market_state: true  so callers can
    distinguish them from a full V1 engine run.

    NOTE: calls private methods of CoreMacroRegimeEngineV1 to reuse the
    allocation tables without duplicating them.  These methods are stable
    pure functions with no side effects.
    """
    from src.macro_regime.core_v1_engine import CoreMacroRegimeEngineV1

    sub_scores = market_state.get("sub_scores", {})
    r_probs = market_state.get("regime_probabilities", {})
    color = market_state.get("color", "orange")

    # growth_score 0-100: 100 = strong growth (no stress)
    growth_score = sub_scores.get("growth", {}).get("score", 50)
    # inflation_score 0-100: 100 = low inflation (inverted scale)
    inflation_score = sub_scores.get("inflation", {}).get("score", 50)

    growth_up = growth_score >= 60 or color == "green"
    inflation_up = inflation_score <= 40  # low score = high inflation pressure

    recession_risk = r_probs.get("recession_risk", 0.2) > 0.5
    liquidity_stress = r_probs.get("liquidity_stress_risk", 0.2) > 0.5

    # Map to All-Weather quadrant
    if growth_up and not inflation_up:
        regime_base = "Goldilocks"
    elif growth_up and inflation_up:
        regime_base = "Reflation"
    elif not growth_up and inflation_up:
        regime_base = "Stagflation"
    elif not growth_up and not inflation_up:
        regime_base = "Disinflation"
    else:
        regime_base = "Transition"

    # Ambiguous orange → Transition if scores are not extreme on either axis
    if color == "orange":
        if not (growth_score > 70 or growth_score < 30):
            if not (inflation_score > 70 or inflation_score < 30):
                regime_base = "Transition"

    regime_overlay = "Recession-risk" if recession_risk else "None"

    risk_score = market_state.get("risk_score", 50)
    confidence = min(80, max(30, risk_score))
    if color == "orange":
        confidence = min(confidence, 60)

    engine = CoreMacroRegimeEngineV1()
    r_stress = recession_risk or liquidity_stress
    allocation = engine._get_core_allocation(regime_base, regime_overlay, r_stress, {})
    core_bucket_pct = engine._get_core_bucket_size(confidence)

    return {
        "timestamp_utc": ts_iso,
        "regime_base": regime_base,
        "regime_overlay": regime_overlay,
        "confidence": confidence,
        "core_bucket_percent_of_total": core_bucket_pct,
        "core_allocation_percent_of_core": allocation,
        "_derived_from_market_state": True,
    }


def _run_all_weather_alignment(snapshot: dict, core_regime: dict, ts_iso: str):
    """Execute all_weather_alignment sub-pipeline. Returns artifact dict or None."""
    from src.all_weather_alignment.mapper import load_assets_mapping, map_snapshot_to_classes
    from src.all_weather_alignment.aggregator import aggregate_actual_weights
    from src.all_weather_alignment.target_builder import build_target_weights
    from src.all_weather_alignment.reconciler import compute_alignment, build_ticker_trades
    from src.all_weather_alignment.writer import build_alignment_artifact

    assets_map = load_assets_mapping("config/assets.yml")
    mp, unk, flags = map_snapshot_to_classes(snapshot, assets_map)
    actuals = aggregate_actual_weights(mp, snapshot.get("cash_pct", 0.0))
    targets = build_target_weights(core_regime)

    gaps, qual, posture, recs = compute_alignment(
        targets, actuals, unk,
        core_regime.get("regime_base", "Transition"),
        core_regime.get("regime_overlay", "None"),
        core_regime.get("confidence", 50),
    )
    trades = build_ticker_trades(mp, gaps, qual)

    qual_dict = {
        "mapping_coverage_pct": round(100.0 - unk, 2),
        "unknown_weight_pct": round(unk, 2),
        "quality_label": qual,
        "flags": flags,
    }

    return build_alignment_artifact(
        ts_iso, ts_iso,
        core_regime.get("timestamp_utc", ts_iso), ts_iso,
        core_regime, qual_dict, targets, actuals, gaps, posture, recs, trades,
    )


def main():
    ts_iso = datetime.now(timezone.utc).isoformat()
    ts_str = ts_iso.replace(":", "").replace("-", "")[:15]

    setup_logging(ts_str)
    logger.info("Starting eToro Portfolio Agent pipeline...")

    try:
        # ------------------------------------------------------------------ #
        # STEP 0 — Market Regime Model (V2)                                   #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 0: Market Regime Model ===")
        from src.scoring.regime_model import evaluate_regimes_and_scores
        from src.collectors.fred_collector import fetch_all_fred
        from src.collectors.market_prices_collector import fetch_all_market_prices

        logger.info("Fetching macro data from FRED...")
        fred_data = fetch_all_fred()
        logger.info("Fetching market prices from Yahoo Finance...")
        market_data = fetch_all_market_prices()

        all_data = {**fred_data, **market_data}
        market_state = evaluate_regimes_and_scores(all_data)
        market_state["timestamp"] = ts_iso

        with open("schemas/market_state.schema.json") as f:
            schema = json.load(f)
        validate(instance=market_state, schema=schema)

        out_file = f"out/market_state_{ts_str}.json"
        with open(out_file, "w") as f:
            json.dump(market_state, f, indent=2)
        logger.info(f"Market state saved to {out_file}")

        # ------------------------------------------------------------------ #
        # STEP 1 — Fetch eToro portfolio                                      #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 1: Fetch eToro portfolio ===")
        from src.fetch_etoro import fetch_portfolio

        if not os.environ.get("ETORO_PUBLIC_API_KEY"):
            logger.info("ETORO_PUBLIC_API_KEY missing — running in DRY MODE with fixture.")
            with open("tests/fixtures/snapshot.json") as f:
                raw_data = json.load(f)
        else:
            raw_data = fetch_portfolio()

        # ------------------------------------------------------------------ #
        # STEP 2 — Normalize                                                  #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 2: Normalize ===")
        from src.normalize import normalize_portfolio
        snapshot = normalize_portfolio(raw_data)

        # ------------------------------------------------------------------ #
        # STEP 3 — Portfolio Overlay (V3)                                     #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 3: Portfolio Overlay (V3) ===")
        from src.portfolio.portfolio_overlay import build_portfolio_state
        portfolio_state = build_portfolio_state(snapshot, market_state)

        with open("schemas/portfolio_state.schema.json") as f:
            portfolio_schema = json.load(f)
        validate(instance=portfolio_state, schema=portfolio_schema)

        out_file_port = f"out/portfolio_state_{ts_str}.json"
        with open(out_file_port, "w") as f:
            json.dump(portfolio_state, f, indent=2)
        logger.info(f"Portfolio state saved to {out_file_port}")

        # ------------------------------------------------------------------ #
        # STEP 3b — Portfolio Interpretation                                  #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 3b: Portfolio Interpretation ===")
        portfolio_interpretation = None
        try:
            from src.portfolio.portfolio_interpreter import interpret_portfolio
            portfolio_interpretation = interpret_portfolio(snapshot, portfolio_state, market_state)
            out_file_interp = f"out/portfolio_interpretation_{ts_str}.json"
            with open(out_file_interp, "w") as f:
                json.dump(portfolio_interpretation, f, indent=2)
            logger.info(
                f"Interpretation: posture={portfolio_interpretation.get('posture_label')} | "
                f"missing_sleeves={len(portfolio_interpretation.get('missing_sleeves', []))} | "
                f"contradictions={len(portfolio_interpretation.get('regime_contradictions', []))}"
            )
        except Exception as e:
            logger.warning(f"Portfolio interpretation step failed (non-fatal): {e}")

        # ------------------------------------------------------------------ #
        # STEP 4 — Decision Engine (V4)                                       #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 4: Decision Engine (V4) ===")
        from src.decision_engine.engine import generate_decisions
        import yaml

        try:
            with open("config/assets.yml") as f:
                assets_config = yaml.safe_load(f) or {}
            valid_tickers = list(assets_config.keys())
        except Exception:
            valid_tickers = []

        for pos in snapshot.get("positions", []):
            t = pos.get("ticker")
            if t and t not in valid_tickers:
                valid_tickers.append(t)

        decisions = generate_decisions(snapshot, market_state, portfolio_state, valid_tickers)

        out_file_decisions = f"out/decisions_{ts_str}.json"
        with open(out_file_decisions, "w") as f:
            json.dump(decisions, f, indent=2)
        logger.info(f"Decisions saved to {out_file_decisions}")

        # ------------------------------------------------------------------ #
        # STEP 5 — Monitoring, Storage (V5)                                   #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 5: Monitoring & Storage (V5) ===")
        from src.monitoring.health_score import compute_health_score
        from src.monitoring.alerts import evaluate_alerts
        from src.monitoring.storage import extract_history_row, append_to_history, create_run_bundle
        from src.publish.publish import zip_run_bundle, generate_markdown_report, optional_google_drive_upload

        summary = compute_health_score(market_state, portfolio_state, decisions)
        summary["timestamp"] = ts_iso

        with open("schemas/summary.schema.json") as f:
            summary_schema = json.load(f)
        validate(instance=summary, schema=summary_schema)

        out_file_summary = f"out/summary_{ts_str}.json"
        with open(out_file_summary, "w") as f:
            json.dump(summary, f, indent=2)

        alerts = evaluate_alerts(market_state, portfolio_state)
        with open("schemas/alerts.schema.json") as f:
            alerts_schema = json.load(f)
        validate(instance=alerts, schema=alerts_schema)

        out_file_alerts = f"out/alerts_{ts_str}.json"
        with open(out_file_alerts, "w") as f:
            json.dump(alerts, f, indent=2)

        logger.info("Appending to history...")
        history_row = extract_history_row(ts_iso, market_state, portfolio_state, decisions, summary)
        append_to_history(history_row)

        logger.info("Creating run bundle...")
        bundle_dir = create_run_bundle(
            ts_str, ts_iso, snapshot, market_state,
            portfolio_state, decisions, summary, alerts,
        )
        zip_path = zip_run_bundle(bundle_dir)

        # ------------------------------------------------------------------ #
        # STEP 5b — All-Weather Alignment                                     #
        # Runs every time: uses V1 engine file if present, otherwise derives  #
        # the core_regime automatically from market_state.                   #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 5b: All-Weather Alignment ===")
        all_weather_alignment = None
        try:
            core_regime_path = f"out/core_regime_state_{ts_str}.json"
            if os.path.exists(core_regime_path):
                with open(core_regime_path) as f:
                    core_regime = json.load(f)
                logger.info("Using V1 engine core_regime from disk.")
            else:
                logger.info("Deriving core_regime from market_state (V1 engine not run).")
                core_regime = _derive_core_regime_from_market_state(market_state, ts_iso)

            out_regime = f"out/core_regime_derived_{ts_str}.json"
            with open(out_regime, "w") as f:
                json.dump(core_regime, f, indent=2)

            all_weather_alignment = _run_all_weather_alignment(snapshot, core_regime, ts_iso)

            if all_weather_alignment:
                out_path_aw = f"out/all_weather_alignment_{ts_str}.json"
                with open(out_path_aw, "w") as f:
                    json.dump(all_weather_alignment, f, indent=2)
                logger.info(
                    f"All-Weather Alignment: "
                    f"posture={all_weather_alignment.get('posture', {}).get('posture')} | "
                    f"regime={core_regime.get('regime_base')}"
                )
        except Exception as awe:
            logger.warning(f"All-Weather Alignment step failed (non-fatal): {awe}")

        # ------------------------------------------------------------------ #
        # STEP 5c — Report generation                                         #
        # ------------------------------------------------------------------ #
        report_path = generate_markdown_report(
            ts_str=ts_str,
            summary=summary,
            alerts=alerts,
            market_state=market_state,
            portfolio_state=portfolio_state,
            all_weather_alignment=all_weather_alignment,
            portfolio_interpretation=portfolio_interpretation,
            snapshot=snapshot,
        )
        logger.info(f"Report generated: {report_path}")
        optional_google_drive_upload(zip_path)

        # ------------------------------------------------------------------ #
        # STEP 6 — Webhook Broadcasting (V6)                                  #
        # ------------------------------------------------------------------ #
        logger.info("=== STEP 6: Webhook Broadcasting (V6) ===")
        from src.publish.notifier import send_webhook_notification
        send_webhook_notification(report_path, ts_str)

        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
