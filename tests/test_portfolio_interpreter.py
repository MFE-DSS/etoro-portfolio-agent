"""
tests/test_portfolio_interpreter.py

Tests for the portfolio interpretation layer.
All tests use synthetic data — no I/O, no external calls.
"""

import pytest
from src.portfolio.portfolio_interpreter import (
    interpret_portfolio,
    _detect_missing_sleeves,
    _assess_regime_fit,
    _compute_posture_label,
)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def snapshot_heavy_tech():
    """US-heavy, tech-concentrated, no bonds or gold."""
    return {
        "date": "2026-03-01T00:00:00Z",
        "currency": "USD",
        "cash_pct": 0.05,
        "positions": [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.25, "pnl_pct": 0.50},
            {"ticker": "MSFT", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.20, "pnl_pct": 0.30},
            {"ticker": "NVDA", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.20, "pnl_pct": 0.80},
            {"ticker": "XOM",  "asset_type": "Equity", "region": "US", "sector": "Energy",     "weight_pct": 0.20, "pnl_pct": 0.10},
            {"ticker": "AMZN", "asset_type": "Equity", "region": "US", "sector": "Consumer Discretionary", "weight_pct": 0.10, "pnl_pct": 0.05},
        ],
    }


@pytest.fixture
def snapshot_balanced():
    """Mixed portfolio with bonds and gold."""
    return {
        "date": "2026-03-01T00:00:00Z",
        "currency": "USD",
        "cash_pct": 0.15,
        "positions": [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US",     "sector": "Technology",     "weight_pct": 0.20, "pnl_pct": 0.50},
            {"ticker": "XOM",  "asset_type": "Equity", "region": "US",     "sector": "Energy",         "weight_pct": 0.25, "pnl_pct": 0.22},
            {"ticker": "TLT",  "asset_type": "ETF",    "region": "US",     "sector": "Government",     "weight_pct": 0.15, "pnl_pct": -0.05},
            {"ticker": "GLD",  "asset_type": "ETF",    "region": "Global", "sector": "Basic Materials", "weight_pct": 0.10, "pnl_pct": 0.055},
            {"ticker": "JNJ",  "asset_type": "Equity", "region": "US",     "sector": "Healthcare",     "weight_pct": 0.15, "pnl_pct": 0.10},
        ],
    }


@pytest.fixture
def portfolio_state_heavy_tech():
    return {
        "portfolio_summary": {
            "total_positions": 5,
            "cash_pct": 0.05,
            "hhi": 0.19,
            "top_1_pct": 0.25,
            "top_4_pct": 0.85,
            "top_10_pct": 0.95,
        },
        "exposures": {
            "by_sector": {
                "Technology": 0.65,
                "Energy": 0.20,
                "Consumer Discretionary": 0.10,
            },
            "by_region": {"US": 0.95},
            "by_asset_type": {"Equity": 0.95},
        },
        "risk_overlay": {
            "macro_regime": {},
            "correlation_buckets": {
                "us_growth": 0.75,
                "energy": 0.20,
                "defensives": 0.0,
                "rates_sensitive": 0.0,
                "commodities": 0.0,
                "quality": 0.0,
                "other": 0.0,
                "unknown": 0.0,
            },
            "flags": [],
        },
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.25, "macro_fit_score": 80, "color": "green", "optionality_consumed": True,  "tags": ["regime_aligned_cyclical", "optionality_consumed_pnl"]},
            {"ticker": "MSFT", "weight_pct": 0.20, "macro_fit_score": 80, "color": "green", "optionality_consumed": False, "tags": ["regime_aligned_cyclical"]},
            {"ticker": "NVDA", "weight_pct": 0.20, "macro_fit_score": 60, "color": "green", "optionality_consumed": True,  "tags": ["regime_aligned_cyclical", "optionality_consumed_pnl"]},
            {"ticker": "XOM",  "weight_pct": 0.20, "macro_fit_score": 80, "color": "green", "optionality_consumed": False, "tags": ["regime_aligned_cyclical"]},
            {"ticker": "AMZN", "weight_pct": 0.10, "macro_fit_score": 80, "color": "green", "optionality_consumed": False, "tags": ["regime_aligned_cyclical"]},
        ],
    }


@pytest.fixture
def portfolio_state_balanced():
    return {
        "portfolio_summary": {
            "total_positions": 5,
            "cash_pct": 0.15,
            "hhi": 0.135,
            "top_1_pct": 0.25,
            "top_4_pct": 0.70,
            "top_10_pct": 0.85,
        },
        "exposures": {
            "by_sector": {
                "Energy": 0.25,
                "Technology": 0.20,
                "Government": 0.15,
                "Healthcare": 0.15,
                "Basic Materials": 0.10,
            },
            "by_region": {"US": 0.75, "Global": 0.10},
            "by_asset_type": {"Equity": 0.60, "ETF": 0.25},
        },
        "risk_overlay": {
            "macro_regime": {},
            "correlation_buckets": {
                "us_growth": 0.20,
                "energy": 0.25,
                "defensives": 0.15,
                "rates_sensitive": 0.15,
                "commodities": 0.10,
                "quality": 0.0,
                "other": 0.0,
                "unknown": 0.0,
            },
            "flags": [],
        },
        "positions": [
            {"ticker": "AAPL", "weight_pct": 0.20, "macro_fit_score": 50, "color": "orange", "optionality_consumed": False, "tags": []},
            {"ticker": "XOM",  "weight_pct": 0.25, "macro_fit_score": 80, "color": "green",  "optionality_consumed": False, "tags": ["regime_aligned_cyclical"]},
            {"ticker": "TLT",  "weight_pct": 0.15, "macro_fit_score": 80, "color": "green",  "optionality_consumed": False, "tags": ["regime_aligned_defensive"]},
            {"ticker": "GLD",  "weight_pct": 0.10, "macro_fit_score": 50, "color": "orange", "optionality_consumed": False, "tags": []},
            {"ticker": "JNJ",  "weight_pct": 0.15, "macro_fit_score": 80, "color": "green",  "optionality_consumed": False, "tags": ["regime_aligned_defensive"]},
        ],
    }


@pytest.fixture
def market_state_green():
    return {"color": "green", "risk_score": 75}


@pytest.fixture
def market_state_orange():
    return {"color": "orange", "risk_score": 50}


@pytest.fixture
def market_state_red():
    return {"color": "red", "risk_score": 25}


# ---------------------------------------------------------------------------
# interpret_portfolio — structure
# ---------------------------------------------------------------------------

class TestInterpretPortfolioStructure:
    def test_returns_required_keys(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        required = [
            "n_positions", "cash_pct", "top5_by_weight", "concentration",
            "by_factor", "by_sector", "by_region", "by_asset_type",
            "missing_sleeves", "redundant_pairs", "regime_contradictions",
            "regime_protections", "posture_label", "narrative_summary",
        ]
        for key in required:
            assert key in result, f"Missing key: {key}"

    def test_n_positions(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert result["n_positions"] == 5

    def test_cash_pct_is_percentage(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert result["cash_pct"] == 15.0  # 0.15 * 100

    def test_top5_length(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert len(result["top5_by_weight"]) <= 5

    def test_top5_has_required_fields(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        for pos in result["top5_by_weight"]:
            assert "ticker" in pos
            assert "weight_pct" in pos
            assert "macro_fit" in pos

    def test_concentration_keys(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        c = result["concentration"]
        assert "hhi" in c
        assert "top1_pct" in c
        assert "top4_pct" in c
        assert "warning" in c
        assert c["warning"] in ("OK", "MODERATE", "HIGH")

    def test_posture_label_is_valid(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert result["posture_label"] in ("ALIGNED", "PARTIALLY_ALIGNED", "MISALIGNED")

    def test_narrative_is_non_empty_string(self, snapshot_balanced, portfolio_state_balanced, market_state_orange):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert isinstance(result["narrative_summary"], str)
        assert len(result["narrative_summary"]) > 10


# ---------------------------------------------------------------------------
# Missing sleeves detection
# ---------------------------------------------------------------------------

class TestMissingSleeveDetection:
    def test_detects_missing_bonds_in_tech_portfolio(self, snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange):
        result = interpret_portfolio(snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Duration / Bonds" in sleeve_names

    def test_detects_missing_gold_in_tech_portfolio(self, snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange):
        result = interpret_portfolio(snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Gold / Inflation Hedge" in sleeve_names

    def test_detects_missing_defensives_in_risk_off(self, snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_red):
        result = interpret_portfolio(snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_red)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Defensive Equities" in sleeve_names

    def test_no_missing_defensives_in_risk_on(self):
        """In a green/risk-on regime, missing defensives should NOT be flagged."""
        buckets = {"us_growth": 0.75, "energy": 0.20, "defensives": 0.0,
                   "rates_sensitive": 0.0, "commodities": 0.0, "quality": 0.0,
                   "other": 0.0, "unknown": 0.0}
        positions = [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.75},
            {"ticker": "XOM",  "asset_type": "Equity", "region": "US", "sector": "Energy",     "weight_pct": 0.20},
        ]
        missing = _detect_missing_sleeves(positions, buckets, "green", 5.0)
        sleeve_names = [s["sleeve"] for s in missing]
        assert "Defensive Equities" not in sleeve_names

    def test_detects_us_concentration(self, snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange):
        result = interpret_portfolio(snapshot_heavy_tech, portfolio_state_heavy_tech, market_state_orange)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Geographic Diversification" in sleeve_names

    def test_no_missing_bonds_when_tlt_held(self):
        """TLT presence should suppress the bonds missing-sleeve warning."""
        buckets = {"rates_sensitive": 0.15, "us_growth": 0.50,
                   "energy": 0.0, "defensives": 0.0, "commodities": 0.0,
                   "quality": 0.0, "other": 0.0, "unknown": 0.0}
        positions = [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.50},
            {"ticker": "TLT",  "asset_type": "ETF",    "region": "US", "sector": "Government", "weight_pct": 0.15},
        ]
        missing = _detect_missing_sleeves(positions, buckets, "orange", 5.0)
        sleeve_names = [s["sleeve"] for s in missing]
        assert "Duration / Bonds" not in sleeve_names

    def test_no_missing_gold_when_gld_held(self):
        buckets = {"commodities": 0.10, "us_growth": 0.50,
                   "rates_sensitive": 0.10, "energy": 0.0, "defensives": 0.0,
                   "quality": 0.0, "other": 0.0, "unknown": 0.0}
        positions = [
            {"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 0.50},
            {"ticker": "GLD",  "asset_type": "ETF",    "region": "Global", "sector": "Basic Materials", "weight_pct": 0.10},
        ]
        missing = _detect_missing_sleeves(positions, buckets, "orange", 5.0)
        sleeve_names = [s["sleeve"] for s in missing]
        assert "Gold / Inflation Hedge" not in sleeve_names


# ---------------------------------------------------------------------------
# Regime fit assessment
# ---------------------------------------------------------------------------

class TestRegimeFitAssessment:
    def test_green_positions_become_protections(self):
        ps_positions = [
            {"ticker": "TLT", "weight_pct": 0.15, "color": "green", "tags": ["regime_aligned_defensive"]},
            {"ticker": "JNJ", "weight_pct": 0.10, "color": "green", "tags": ["regime_aligned_defensive"]},
        ]
        contradictions, protections = _assess_regime_fit(ps_positions)
        assert len(protections) == 2
        assert len(contradictions) == 0

    def test_red_positions_become_contradictions(self):
        ps_positions = [
            {"ticker": "NVDA", "weight_pct": 0.20, "color": "red", "tags": ["regime_mismatch_cyclical"]},
        ]
        contradictions, protections = _assess_regime_fit(ps_positions)
        assert len(contradictions) == 1
        assert contradictions[0]["ticker"] == "NVDA"

    def test_tiny_positions_ignored(self):
        """Positions < 3% should not be flagged to avoid noise."""
        ps_positions = [
            {"ticker": "TINY", "weight_pct": 0.02, "color": "red", "tags": ["regime_mismatch_cyclical"]},
        ]
        contradictions, _ = _assess_regime_fit(ps_positions)
        assert len(contradictions) == 0

    def test_sorted_by_weight_descending(self):
        ps_positions = [
            {"ticker": "A", "weight_pct": 0.05, "color": "red", "tags": ["regime_mismatch_cyclical"]},
            {"ticker": "B", "weight_pct": 0.30, "color": "red", "tags": ["regime_mismatch_cyclical"]},
        ]
        contradictions, _ = _assess_regime_fit(ps_positions)
        assert contradictions[0]["ticker"] == "B"


# ---------------------------------------------------------------------------
# Posture label
# ---------------------------------------------------------------------------

class TestPostureLabel:
    def test_aligned_when_no_red_no_missing(self):
        assert _compute_posture_label(0.0, []) == "ALIGNED"

    def test_partially_aligned_moderate_red(self):
        assert _compute_posture_label(0.20, [{"sleeve": "X"}]) == "PARTIALLY_ALIGNED"

    def test_misaligned_heavy_red(self):
        assert _compute_posture_label(0.40, []) == "MISALIGNED"

    def test_misaligned_many_missing_sleeves(self):
        sleeves = [{"sleeve": str(i)} for i in range(4)]
        assert _compute_posture_label(0.0, sleeves) == "MISALIGNED"


# ---------------------------------------------------------------------------
# Balanced portfolio → aligned
# ---------------------------------------------------------------------------

class TestBalancedPortfolioAlignment:
    def test_balanced_portfolio_is_partially_or_aligned(
        self, snapshot_balanced, portfolio_state_balanced, market_state_orange
    ):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        assert result["posture_label"] in ("ALIGNED", "PARTIALLY_ALIGNED")

    def test_no_missing_bonds_in_balanced(
        self, snapshot_balanced, portfolio_state_balanced, market_state_orange
    ):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Duration / Bonds" not in sleeve_names

    def test_no_missing_gold_in_balanced(
        self, snapshot_balanced, portfolio_state_balanced, market_state_orange
    ):
        result = interpret_portfolio(snapshot_balanced, portfolio_state_balanced, market_state_orange)
        sleeve_names = [s["sleeve"] for s in result["missing_sleeves"]]
        assert "Gold / Inflation Hedge" not in sleeve_names


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_empty_positions(self):
        snapshot = {"date": "2026-01-01T00:00:00Z", "currency": "USD", "cash_pct": 1.0, "positions": []}
        portfolio_state = {
            "portfolio_summary": {"total_positions": 0, "cash_pct": 1.0, "hhi": 0.0, "top_1_pct": 0.0, "top_4_pct": 0.0, "top_10_pct": 0.0},
            "exposures": {"by_sector": {}, "by_region": {}, "by_asset_type": {}},
            "risk_overlay": {"macro_regime": {}, "correlation_buckets": {}, "flags": []},
            "positions": [],
        }
        market_state = {"color": "orange", "risk_score": 50}
        result = interpret_portfolio(snapshot, portfolio_state, market_state)
        assert result["n_positions"] == 0
        assert result["top5_by_weight"] == []
        assert isinstance(result["narrative_summary"], str)

    def test_single_position(self):
        snapshot = {
            "date": "2026-01-01T00:00:00Z", "currency": "USD", "cash_pct": 0.0,
            "positions": [{"ticker": "AAPL", "asset_type": "Equity", "region": "US", "sector": "Technology", "weight_pct": 1.0}],
        }
        portfolio_state = {
            "portfolio_summary": {"total_positions": 1, "cash_pct": 0.0, "hhi": 1.0, "top_1_pct": 1.0, "top_4_pct": 1.0, "top_10_pct": 1.0},
            "exposures": {"by_sector": {"Technology": 1.0}, "by_region": {"US": 1.0}, "by_asset_type": {"Equity": 1.0}},
            "risk_overlay": {"macro_regime": {}, "correlation_buckets": {"us_growth": 1.0}, "flags": []},
            "positions": [{"ticker": "AAPL", "weight_pct": 1.0, "color": "green", "tags": [], "optionality_consumed": False}],
        }
        market_state = {"color": "green", "risk_score": 80}
        result = interpret_portfolio(snapshot, portfolio_state, market_state)
        assert result["concentration"]["warning"] == "HIGH"
        assert result["n_positions"] == 1
