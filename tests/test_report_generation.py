"""
tests/test_report_generation.py

Smoke tests for generate_markdown_report().
Verifies section presence, graceful degradation, and no-crash behaviour.
"""

import os
import json
import pytest
import tempfile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_market_state():
    return {
        "risk_score": 60,
        "color": "orange",
        "timestamp": "2026-03-01T10:00:00Z",
        "sub_scores": {
            "usd_stress": {"score": 60, "color": "orange"},
            "commodities_stress": {"score": 60, "color": "orange"},
        },
        "regime_probabilities": {
            "recession_risk": 0.2,
            "liquidity_stress_risk": 0.1,
            "inflation_resurgence_risk": 0.2,
            "policy_shock_risk": 0.1,
        },
        "indicators": {
            "volatility": {"vix_level": 18},
            "trend": {"ndx": {"price": 19000, "ma200": 17000}},
            "credit": {"hy_spread_level": 3.5},
            "rates": {"yield_curve_10y_2y": 0.3},
            "usd_gold": {"dxy_above_ma50": False},
            "inflation": {"cpi_headline_yoy": 2.5},
            "growth": {"pmi_level": 52},
        },
    }


@pytest.fixture
def minimal_portfolio_state():
    return {
        "timestamp": "2026-03-01T10:00:00Z",
        "portfolio_summary": {
            "total_positions": 5,
            "cash_pct": 0.15,
            "hhi": 0.135,
            "top_1_pct": 0.25,
            "top_4_pct": 0.70,
            "top_10_pct": 0.85,
        },
        "exposures": {
            "by_sector": {"Technology": 0.40, "Energy": 0.25},
            "by_region": {"US": 0.85, "Global": 0.10},
            "by_asset_type": {"Equity": 0.70, "ETF": 0.15},
        },
        "risk_overlay": {
            "macro_regime": {
                "regime_state": "NEUTRAL",
                "p_bull": 0.55,
                "p_drawdown_20": 0.10,
                "p_drawdown_10": 0.15,
            },
            "correlation_buckets": {
                "us_growth": 0.40, "energy": 0.25, "defensives": 0.15,
                "rates_sensitive": 0.15, "commodities": 0.05,
                "quality": 0.0, "other": 0.0, "unknown": 0.0,
            },
            "flags": [],
        },
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.25, "macro_fit_score": 70, "color": "green", "optionality_consumed": False, "tags": []},
            {"ticker": "XOM",  "weight_pct": 0.25, "macro_fit_score": 70, "color": "green", "optionality_consumed": False, "tags": []},
        ],
    }


@pytest.fixture
def minimal_summary():
    return {
        "health_score": 80,
        "health_color": "green",
        "breakdown": {"base_score": 100, "penalties": {}},
        "top_risks": [],
        "top_opportunities": [],
    }


@pytest.fixture
def minimal_alerts():
    return {"timestamp": "2026-03-01T10:00:00Z", "alerts": []}


@pytest.fixture
def minimal_snapshot():
    return {
        "date": "2026-03-01T10:00:00Z",
        "currency": "USD",
        "cash_pct": 0.15,
        "positions": [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.20, "pnl_pct": 0.50},
            {"ticker": "XOM",  "asset_type": "Equity", "region": "US", "sector": "Energy",     "weight_pct": 0.25, "pnl_pct": 0.22},
            {"ticker": "TLT",  "asset_type": "ETF",    "region": "US", "sector": "Government", "weight_pct": 0.15, "pnl_pct": -0.05},
            {"ticker": "GLD",  "asset_type": "ETF",    "region": "Global", "sector": "Basic Materials", "weight_pct": 0.10, "pnl_pct": 0.055},
            {"ticker": "JNJ",  "asset_type": "Equity", "region": "US", "sector": "Healthcare", "weight_pct": 0.15, "pnl_pct": 0.10},
        ],
    }


@pytest.fixture
def minimal_interpretation():
    return {
        "n_positions": 5,
        "cash_pct": 15.0,
        "top5_by_weight": [
            {"ticker": "XOM",  "weight_pct": 25.0, "sector": "Energy",      "asset_type": "Equity", "pnl_pct": 22.0, "macro_fit": "green"},
            {"ticker": "AAPL", "weight_pct": 20.0, "sector": "Technology",  "asset_type": "Equity", "pnl_pct": 50.0, "macro_fit": "green"},
            {"ticker": "TLT",  "weight_pct": 15.0, "sector": "Government",  "asset_type": "ETF",    "pnl_pct": -5.0, "macro_fit": "green"},
            {"ticker": "JNJ",  "weight_pct": 15.0, "sector": "Healthcare",  "asset_type": "Equity", "pnl_pct": 10.0, "macro_fit": "green"},
            {"ticker": "GLD",  "weight_pct": 10.0, "sector": "Basic Materials", "asset_type": "ETF", "pnl_pct": 5.5, "macro_fit": "orange"},
        ],
        "concentration": {"hhi": 0.135, "top1_pct": 25.0, "top4_pct": 70.0, "warning": "MODERATE"},
        "by_factor": {"energy": 25.0, "us_growth": 20.0, "rates_sensitive": 15.0, "defensives": 15.0, "commodities": 10.0},
        "by_sector": {"Energy": 25.0, "Technology": 20.0, "Government": 15.0, "Healthcare": 15.0, "Basic Materials": 10.0},
        "by_region": {"US": 75.0, "Global": 10.0},
        "by_asset_type": {"Equity": 60.0, "ETF": 25.0},
        "missing_sleeves": [],
        "redundant_pairs": [],
        "regime_contradictions": [],
        "regime_protections": [
            {"ticker": "TLT", "weight_pct": 15.0, "reason": "regime aligned defensive"},
            {"ticker": "JNJ", "weight_pct": 15.0, "reason": "regime aligned defensive"},
        ],
        "posture_label": "ALIGNED",
        "narrative_summary": "5 positions, 15% cash. Concentration is moderate (HHI 0.135). In the current transitional regime, portfolio appears aligned.",
    }


# ---------------------------------------------------------------------------
# Report generation — with monkey-patched out_dir
# ---------------------------------------------------------------------------

def _run_report(tmp_path, ms, ps, summary, alerts, snapshot, interpretation=None, aw=None):
    """Helper: patch the report output to a temp dir, run generate_markdown_report."""
    import src.publish.publish as pub_mod

    original_report_path_fn = pub_mod.generate_markdown_report

    ts_str = "20260301T100000"

    # Patch report_path to use tmp_path
    out_dir = str(tmp_path)
    report_path = os.path.join(out_dir, f"report_{ts_str}.md")

    # Temporarily redirect the function's internal os.makedirs / path
    # We do this by monkeypatching the out dir reference inside the function
    import unittest.mock as mock
    with mock.patch("os.path.join", wraps=os.path.join) as mock_join:
        # We can't easily monkeypatch the internal path, so just call it and
        # check the returned path and that a file exists somewhere.
        result_path = pub_mod.generate_markdown_report(
            ts_str=ts_str,
            summary=summary,
            alerts=alerts,
            market_state=ms,
            portfolio_state=ps,
            all_weather_alignment=aw,
            portfolio_interpretation=interpretation,
            snapshot=snapshot,
        )

    return result_path


class TestReportGeneration:
    def test_report_file_created(
        self, tmp_path, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot, minimal_interpretation
    ):
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100000",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=minimal_interpretation,
            snapshot=minimal_snapshot,
        )
        assert os.path.exists(path), f"Report not created at {path}"

    def test_report_contains_7_sections(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot, minimal_interpretation
    ):
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100001",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=minimal_interpretation,
            snapshot=minimal_snapshot,
        )
        with open(path) as f:
            content = f.read()

        for section in [
            "## 1. Executive Summary",
            "## 2. Current Macro Regime",
            "## 3. Portfolio Snapshot",
            "## 4. Regime Alignment Assessment",
            "## 5. Risks",
            "## 6. Watchpoints",
            "## 7. Machine-Readable Appendix",
        ]:
            assert section in content, f"Section missing from report: {section}"

    def test_report_contains_ticker_table(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot, minimal_interpretation
    ):
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100002",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=minimal_interpretation,
            snapshot=minimal_snapshot,
        )
        with open(path) as f:
            content = f.read()
        assert "XOM" in content
        assert "AAPL" in content

    def test_report_degrades_without_interpretation(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot
    ):
        """Report should not crash when portfolio_interpretation is None."""
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100003",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=None,
            snapshot=minimal_snapshot,
        )
        assert os.path.exists(path)
        with open(path) as f:
            content = f.read()
        assert "## 1. Executive Summary" in content
        assert "## 2. Current Macro Regime" in content

    def test_report_contains_machine_readable_json(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot, minimal_interpretation
    ):
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100004",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=minimal_interpretation,
            snapshot=minimal_snapshot,
        )
        with open(path) as f:
            content = f.read()
        assert "```json" in content
        assert "health_score" in content

    def test_report_contains_regime_risk_probabilities(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_alerts, minimal_snapshot
    ):
        from src.publish.publish import generate_markdown_report
        path = generate_markdown_report(
            ts_str="20260301T100005",
            summary=minimal_summary,
            alerts=minimal_alerts,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            snapshot=minimal_snapshot,
        )
        with open(path) as f:
            content = f.read()
        assert "Recession" in content
        assert "Liquidity Stress" in content

    def test_report_with_active_alerts(
        self, minimal_market_state, minimal_portfolio_state,
        minimal_summary, minimal_snapshot, minimal_interpretation
    ):
        from src.publish.publish import generate_markdown_report
        alerts_with_trigger = {
            "timestamp": "2026-03-01T10:00:00Z",
            "alerts": [
                {"rule_name": "High Concentration", "severity": "warning",
                 "message": "Top 4 positions exceed 60%", "trigger_value": 0.70},
            ],
        }
        path = generate_markdown_report(
            ts_str="20260301T100006",
            summary=minimal_summary,
            alerts=alerts_with_trigger,
            market_state=minimal_market_state,
            portfolio_state=minimal_portfolio_state,
            portfolio_interpretation=minimal_interpretation,
            snapshot=minimal_snapshot,
        )
        with open(path) as f:
            content = f.read()
        assert "High Concentration" in content


# ---------------------------------------------------------------------------
# normalize_portfolio — pre-normalized passthrough
# ---------------------------------------------------------------------------

class TestNormalizePassthrough:
    def test_pre_normalized_fixture_passes_through(self, minimal_snapshot):
        """A pre-normalized snapshot (fixture) should pass validation unchanged."""
        from src.normalize import normalize_portfolio, _is_pre_normalized
        assert _is_pre_normalized(minimal_snapshot)

    def test_non_normalized_api_response_detected(self):
        raw = {"clientPortfolio": {"positions": [], "credit": 100.0}}
        from src.normalize import _is_pre_normalized
        assert not _is_pre_normalized(raw)
