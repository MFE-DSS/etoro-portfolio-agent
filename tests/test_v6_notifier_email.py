"""
test_v6_notifier_email.py

Tests for generate_markdown_report() output.
Updated to match the 7-section Portfolio Intelligence Brief format.
"""
import pytest
import src.publish.publish as pub
from src.publish.publish import generate_markdown_report


def _make_state():
    """Minimal state objects for report generation tests."""
    summary = {
        "health_score": 30,
        "health_color": "red",
        "breakdown": {"base_score": 100, "penalties": {"Drawdown": -70}},
        "top_risks": ["Test Risk"],
        "top_opportunities": [],
    }
    alerts = {"alerts": []}
    market_state = {
        "risk_score": 62,
        "color": "orange",
        "timestamp": "2026-03-04T12:00:00Z",
        "sub_scores": {
            "inflation": {"score": 80, "color": "orange"},
            "usd_stress": {"score": 60, "color": "orange"},
            "commodities_stress": {"score": 60, "color": "orange"},
        },
        "regime_probabilities": {
            "recession_risk": 0.15,
            "liquidity_stress_risk": 0.10,
            "inflation_resurgence_risk": 0.20,
            "policy_shock_risk": 0.05,
        },
        "indicators": {
            "volatility": {"vix_level": 20.0},
            "trend": {"ndx": {"price": 19000, "ma200": 17000}},
            "credit": {"hy_spread_level": 3.5},
            "rates": {"yield_curve_10y_2y": 0.3},
            "usd_gold": {"dxy_above_ma50": False},
            "inflation": {"cpi_headline_yoy": 2.5},
            "growth": {"pmi_level": 52},
        },
    }
    portfolio_state = {
        "cash_pct": 0.1643,
        "portfolio_summary": {"cash_pct": 0.1643, "hhi": 0.10, "total_positions": 0,
                               "top_1_pct": 0.0, "top_4_pct": 0.0, "top_10_pct": 0.0},
        "exposures": {
            "by_sector": {}, "by_region": {}, "by_asset_type": {}
        },
        "risk_overlay": {
            "macro_regime": {
                "regime_state": "RISK_ON",
                "macro_score": 80.0,
                "traffic_light": "GREEN",
                "p_bull": 0.8,
                "p_drawdown_10": 0.0,
                "p_drawdown_20": 0.0,
                "p_drawdown_composite": 0.0,
                "buy_the_dip_ok": True,
                "recommended_action": "INCREASE_BETA_BUCKET_A",
            },
            "correlation_buckets": {},
            "flags": ["MISSING_ASSET_METADATA", "PROBA_DEGENERATE_EVENTS"],
        },
        "positions": [],
    }
    return summary, alerts, market_state, portfolio_state


def test_report_has_seven_sections(tmp_path):
    summary, alerts, market_state, portfolio_state = _make_state()

    import os
    original_join = os.path.join
    report_file = str(tmp_path / "test_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120000", summary, alerts, market_state, portfolio_state, None
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    for section in [
        "## 1. Executive Summary",
        "## 2. Current Macro Regime",
        "## 3. Portfolio Snapshot",
        "## 4. Regime Alignment Assessment",
        "## 5. Risks",
        "## 6. Watchpoints",
        "## 7. Machine-Readable Appendix",
    ]:
        assert section in content, f"Missing section: {section}"


def test_posture_neutral_when_risk_score_62(tmp_path):
    """risk_score=62, no V5 p_drawdown_20 → NEUTRAL posture expected."""
    summary, alerts, market_state, portfolio_state = _make_state()
    # p_drawdown_20 = 0.0 → V5 degenerate → fall through to heuristic
    # risk_score=62 → NEUTRAL band (40-70)
    portfolio_state["risk_overlay"]["macro_regime"]["p_drawdown_20"] = 0.0

    import os
    original_join = os.path.join
    report_file = str(tmp_path / "neutral_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120010", summary, alerts, market_state, portfolio_state, None
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    assert "NEUTRAL" in content


def test_posture_risk_on_with_v5_green(tmp_path):
    """When V5 traffic_light=GREEN with non-degenerate p_drawdown_20 → RISK-ON."""
    summary, alerts, market_state, portfolio_state = _make_state()
    portfolio_state["risk_overlay"]["macro_regime"]["p_drawdown_20"] = 0.10

    import os
    original_join = os.path.join
    report_file = str(tmp_path / "risk_on_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120020", summary, alerts, market_state, portfolio_state, None
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    assert "RISK-ON" in content


def test_all_weather_alignment_section(tmp_path):
    """When all_weather_alignment is provided, its posture and briefs appear."""
    summary, alerts, market_state, portfolio_state = _make_state()

    all_weather_alignment = {
        "posture": {"posture": "RISK_OFF", "confidence_label": "HIGH", "posture_conflict": True},
        "brief_bullets": [
            "Derived posture 'RISK_OFF' (HIGH confidence) mapped from regime 'Stagflation'.",
            "CRITICAL: Portfolio alignment strongly diverges from the safety requirements of the active regime.",
            "Alignment Quality is MEDIUM (2.0% of portfolio lacks class mappings).",
        ],
        "recommended_actions": {
            "top_3_actions": [
                {"action": "TRIM", "asset": "Global Equities - Quality", "why": "Overweight target by 15.0%"},
            ],
            "notes": ["CRITICAL: Severe posture conflict detected. Address risk exposures immediately."],
        },
        "gaps_total_pct": [],
        "macro_regime": {
            "regime_base": "Stagflation",
            "regime_overlay": "None",
            "confidence": 75,
        },
    }

    import os
    original_join = os.path.join
    report_file = str(tmp_path / "aw_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120030", summary, alerts, market_state, portfolio_state,
            all_weather_alignment
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    assert "RISK_OFF" in content
    assert "Stagflation" in content
    assert "TRIM" in content
    assert "Derived posture" in content


def test_report_contains_regime_probabilities(tmp_path):
    summary, alerts, market_state, portfolio_state = _make_state()

    import os
    original_join = os.path.join
    report_file = str(tmp_path / "probs_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120040", summary, alerts, market_state, portfolio_state, None
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    assert "Recession" in content
    assert "Liquidity Stress" in content
    assert "Inflation" in content


def test_machine_readable_appendix_is_valid_json(tmp_path):
    summary, alerts, market_state, portfolio_state = _make_state()

    import os
    import json
    original_join = os.path.join
    report_file = str(tmp_path / "json_report.md")

    def mock_join(*args):
        if args and "report_" in str(args[-1]):
            return report_file
        return original_join(*args)

    pub.os.path.join = mock_join
    try:
        report_path = pub.generate_markdown_report(
            "2026-03-04T120050", summary, alerts, market_state, portfolio_state, None
        )
        with open(report_path) as f:
            content = f.read()
    finally:
        pub.os.path.join = original_join

    # Extract JSON block between ```json and ```
    start = content.find("```json\n") + len("```json\n")
    end = content.find("\n```", start)
    assert start > len("```json\n"), "No JSON block found"
    json_block = content[start:end]
    parsed = json.loads(json_block)  # should not raise
    assert "health_score" in parsed
