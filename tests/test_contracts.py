"""
tests/test_contracts.py

Tests for src/contracts.py — the shared data contract layer.

Coverage:
  - PortfolioPosition: to_dict, from_dict, optional fields, round-trip
  - PortfolioSnapshot: to_dict, from_dict, empty positions, round-trip
  - SubScore: to_dict, from_dict
  - HeuristicMarketState: to_dict, from_dict, round-trip
  - RegimeOutput: from_heuristic_market_state(), from_core_v1_output(), to_dict
  - PortfolioDiagnosticsPosition: to_dict, from_dict
  - PortfolioSummary: to_dict, from_dict
  - PortfolioState: to_dict, from_dict, round-trip
  - ReportContext: construction, helpers, regime_output() bridge, alignment flag
  - Integration: normalize.py → PortfolioSnapshot round-trip
"""

import pytest
from datetime import datetime, timezone

from src.contracts import (
    PortfolioPosition,
    PortfolioSnapshot,
    SubScore,
    HeuristicMarketState,
    RegimeOutput,
    PortfolioDiagnosticsPosition,
    PortfolioSummary,
    PortfolioState,
    ReportContext,
)


# ---------------------------------------------------------------------------
# Test fixtures / sample data
# ---------------------------------------------------------------------------

_TIMESTAMP = "2026-03-15T10:00:00+00:00"


def _sample_position_dict(**kwargs):
    base = {
        "ticker": "AAPL",
        "asset_type": "Equity",
        "region": "US",
        "sector": "Technology",
        "weight_pct": 0.2,
    }
    base.update(kwargs)
    return base


def _sample_position():
    return PortfolioPosition(
        ticker="AAPL",
        asset_type="Equity",
        region="US",
        sector="Technology",
        weight_pct=0.2,
    )


def _sample_snapshot_dict():
    return {
        "date": _TIMESTAMP,
        "currency": "USD",
        "cash_pct": 0.15,
        "positions": [
            _sample_position_dict(),
            _sample_position_dict(ticker="TLT", asset_type="ETF", sector="Government", weight_pct=0.1),
        ],
    }


def _sample_market_state_dict():
    return {
        "timestamp": _TIMESTAMP,
        "risk_score": 72,
        "color": "green",
        "sub_scores": {
            "risk": {"score": 75, "color": "green"},
            "growth": {"score": 80, "color": "green"},
            "inflation": {"score": 60, "color": "orange"},
        },
        "regime_probabilities": {
            "recession_risk": 0.1,
            "policy_shock_risk": 0.2,
            "inflation_resurgence_risk": 0.15,
            "liquidity_stress_risk": 0.05,
        },
        "indicators": {
            "trend": {"spx": {"above_ma50": True, "above_ma200": True}},
            "volatility": {"vix_level": 14.5},
        },
    }


def _sample_core_v1_output():
    return {
        "timestamp_utc": _TIMESTAMP,
        "regime_base": "Goldilocks",
        "regime_overlay": "None",
        "confidence": 80,
        "signals": {
            "growth_signal": "up",
            "inflation_signal": "down",
        },
        "core_bucket_percent_of_total": 80,
        "core_allocation_percent_of_core": [
            {"asset": "Global Equities - Quality", "weight": 60},
        ],
        "risk_controls": {"rebalance_frequency": "monthly"},
        "monitoring_next_2_weeks": [],
    }


def _sample_portfolio_state_dict():
    return {
        "timestamp": _TIMESTAMP,
        "portfolio_summary": {
            "total_positions": 3,
            "cash_pct": 0.15,
            "hhi": 0.12,
            "top_1_pct": 0.25,
            "top_4_pct": 0.70,
            "top_10_pct": 0.95,
        },
        "exposures": {
            "by_sector": {"Technology": 0.35},
            "by_region": {"US": 0.80},
            "by_asset_type": {"Equity": 0.75},
        },
        "risk_overlay": {
            "macro_regime": {
                "regime_state": "RISK_ON",
                "macro_score": 72.0,
                "traffic_light": "GREEN",
                "p_drawdown_10": 0.05,
                "p_drawdown_20": 0.02,
                "p_drawdown_composite": 0.03,
                "p_bull": 0.8,
                "buy_the_dip_ok": True,
                "recommended_action": "INCREASE_BETA_BUCKET_A",
            },
            "correlation_buckets": {
                "energy": 0.1, "defensives": 0.05, "quality": 0.35,
                "us_growth": 0.30, "commodities": 0.05,
                "rates_sensitive": 0.05, "other": 0.05, "unknown": 0.05,
            },
            "flags": [],
        },
        "positions": [
            {
                "ticker": "AAPL",
                "weight_pct": 0.20,
                "macro_fit_score": 80,
                "color": "green",
                "optionality_consumed": False,
                "tags": ["regime_aligned_cyclical"],
            },
        ],
    }


# ---------------------------------------------------------------------------
# PortfolioPosition tests
# ---------------------------------------------------------------------------

class TestPortfolioPosition:
    def test_to_dict_required_fields(self):
        pos = _sample_position()
        d = pos.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["asset_type"] == "Equity"
        assert d["region"] == "US"
        assert d["sector"] == "Technology"
        assert d["weight_pct"] == 0.2

    def test_to_dict_excludes_none_optionals(self):
        pos = _sample_position()
        d = pos.to_dict()
        assert "price" not in d
        assert "avg_open" not in d
        assert "pnl_pct" not in d

    def test_to_dict_includes_optionals_when_set(self):
        pos = PortfolioPosition(
            ticker="MSFT", asset_type="Equity", region="US",
            sector="Technology", weight_pct=0.15,
            price=350.0, avg_open=300.0, pnl_pct=0.17
        )
        d = pos.to_dict()
        assert d["price"] == 350.0
        assert d["avg_open"] == 300.0
        assert d["pnl_pct"] == 0.17

    def test_from_dict_required_fields(self):
        pos = PortfolioPosition.from_dict(_sample_position_dict())
        assert pos.ticker == "AAPL"
        assert pos.asset_type == "Equity"
        assert pos.weight_pct == 0.2
        assert pos.price is None

    def test_from_dict_optional_fields(self):
        d = _sample_position_dict(price=150.0, pnl_pct=0.5)
        pos = PortfolioPosition.from_dict(d)
        assert pos.price == 150.0
        assert pos.pnl_pct == 0.5

    def test_round_trip(self):
        original = _sample_position_dict()
        pos = PortfolioPosition.from_dict(original)
        result = pos.to_dict()
        assert result["ticker"] == original["ticker"]
        assert result["weight_pct"] == original["weight_pct"]

    def test_unmapped_ticker_is_preserved(self):
        d = _sample_position_dict(ticker="UNMAPPED_99999", asset_type="Unknown",
                                   region="Unknown", sector="Unknown")
        pos = PortfolioPosition.from_dict(d)
        assert pos.ticker == "UNMAPPED_99999"
        out = pos.to_dict()
        assert out["ticker"] == "UNMAPPED_99999"


# ---------------------------------------------------------------------------
# PortfolioSnapshot tests
# ---------------------------------------------------------------------------

class TestPortfolioSnapshot:
    def test_to_dict_structure(self):
        snap = PortfolioSnapshot(
            date=_TIMESTAMP,
            currency="USD",
            cash_pct=0.15,
            positions=[_sample_position()],
        )
        d = snap.to_dict()
        assert d["date"] == _TIMESTAMP
        assert d["currency"] == "USD"
        assert d["cash_pct"] == 0.15
        assert len(d["positions"]) == 1
        assert d["positions"][0]["ticker"] == "AAPL"

    def test_from_dict(self):
        snap = PortfolioSnapshot.from_dict(_sample_snapshot_dict())
        assert snap.currency == "USD"
        assert snap.cash_pct == 0.15
        assert len(snap.positions) == 2
        assert snap.positions[0].ticker == "AAPL"
        assert snap.positions[1].ticker == "TLT"

    def test_empty_positions(self):
        d = {"date": _TIMESTAMP, "currency": "USD", "cash_pct": 1.0, "positions": []}
        snap = PortfolioSnapshot.from_dict(d)
        assert snap.positions == []
        assert snap.to_dict()["positions"] == []

    def test_round_trip(self):
        original = _sample_snapshot_dict()
        snap = PortfolioSnapshot.from_dict(original)
        result = snap.to_dict()
        assert result["cash_pct"] == original["cash_pct"]
        assert len(result["positions"]) == len(original["positions"])
        assert result["positions"][0]["ticker"] == "AAPL"

    def test_from_dict_positions_are_typed(self):
        snap = PortfolioSnapshot.from_dict(_sample_snapshot_dict())
        for pos in snap.positions:
            assert isinstance(pos, PortfolioPosition)


# ---------------------------------------------------------------------------
# SubScore tests
# ---------------------------------------------------------------------------

class TestSubScore:
    def test_to_dict(self):
        s = SubScore(score=75, color="green")
        assert s.to_dict() == {"score": 75, "color": "green"}

    def test_from_dict(self):
        s = SubScore.from_dict({"score": 40, "color": "orange"})
        assert s.score == 40
        assert s.color == "orange"

    def test_round_trip(self):
        original = {"score": 20, "color": "red"}
        assert SubScore.from_dict(original).to_dict() == original


# ---------------------------------------------------------------------------
# HeuristicMarketState tests
# ---------------------------------------------------------------------------

class TestHeuristicMarketState:
    def test_from_dict(self):
        ms = HeuristicMarketState.from_dict(_sample_market_state_dict())
        assert ms.risk_score == 72
        assert ms.color == "green"
        assert "risk" in ms.sub_scores
        assert isinstance(ms.sub_scores["risk"], SubScore)
        assert ms.sub_scores["risk"].score == 75

    def test_to_dict_structure(self):
        ms = HeuristicMarketState.from_dict(_sample_market_state_dict())
        d = ms.to_dict()
        assert d["risk_score"] == 72
        assert d["color"] == "green"
        assert "sub_scores" in d
        assert d["sub_scores"]["risk"]["score"] == 75
        assert "regime_probabilities" in d
        assert "indicators" in d

    def test_round_trip(self):
        original = _sample_market_state_dict()
        ms = HeuristicMarketState.from_dict(original)
        result = ms.to_dict()
        assert result["risk_score"] == original["risk_score"]
        assert result["color"] == original["color"]
        assert result["regime_probabilities"]["recession_risk"] == 0.1

    def test_regime_probabilities_are_preserved(self):
        ms = HeuristicMarketState.from_dict(_sample_market_state_dict())
        assert ms.regime_probabilities["recession_risk"] == 0.1
        assert ms.regime_probabilities["policy_shock_risk"] == 0.2


# ---------------------------------------------------------------------------
# RegimeOutput tests — from_heuristic_market_state
# ---------------------------------------------------------------------------

class TestRegimeOutputFromHeuristic:
    def test_engine_id(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        assert ro.engine_id == "heuristic_v2"

    def test_traffic_light_maps_correctly(self):
        for color, expected_tl in [("green", "GREEN"), ("orange", "ORANGE"), ("red", "RED")]:
            d = {**_sample_market_state_dict(), "color": color}
            ro = RegimeOutput.from_heuristic_market_state(d)
            assert ro.traffic_light == expected_tl

    def test_regime_label_maps_from_color(self):
        d = {**_sample_market_state_dict(), "color": "green"}
        ro = RegimeOutput.from_heuristic_market_state(d)
        assert ro.regime_label == "Risk-On"

        d["color"] = "red"
        ro = RegimeOutput.from_heuristic_market_state(d)
        assert ro.regime_label == "Risk-Off"

    def test_risk_score_preserved(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        assert ro.risk_score == 72

    def test_p_drawdown_20_is_none_for_v2(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        assert ro.p_drawdown_20 is None, "V2 heuristic does not produce p_drawdown_20"

    def test_p_recession_extracted(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        assert ro.p_recession == 0.1

    def test_raw_is_preserved(self):
        d = _sample_market_state_dict()
        ro = RegimeOutput.from_heuristic_market_state(d)
        assert ro.raw["risk_score"] == 72

    def test_to_dict_does_not_include_none_p_drawdown(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        d = ro.to_dict()
        assert "p_drawdown_20" not in d  # None fields excluded

    def test_regime_probabilities_forwarded(self):
        ro = RegimeOutput.from_heuristic_market_state(_sample_market_state_dict())
        assert ro.regime_probabilities["recession_risk"] == 0.1


# ---------------------------------------------------------------------------
# RegimeOutput tests — from_core_v1_output
# ---------------------------------------------------------------------------

class TestRegimeOutputFromCoreV1:
    def test_engine_id(self):
        ro = RegimeOutput.from_core_v1_output(_sample_core_v1_output())
        assert ro.engine_id == "core_v1"

    def test_goldilocks_maps_to_green(self):
        ro = RegimeOutput.from_core_v1_output(_sample_core_v1_output())
        assert ro.traffic_light == "GREEN"
        assert ro.risk_score >= 65

    def test_stagflation_maps_to_red(self):
        d = {**_sample_core_v1_output(), "regime_base": "Stagflation", "regime_overlay": "None"}
        ro = RegimeOutput.from_core_v1_output(d)
        assert ro.traffic_light == "RED"

    def test_recession_overlay_maps_to_red(self):
        d = {**_sample_core_v1_output(), "regime_base": "Goldilocks", "regime_overlay": "Recession-risk"}
        ro = RegimeOutput.from_core_v1_output(d)
        assert ro.traffic_light == "RED"

    def test_transition_maps_to_orange(self):
        d = {**_sample_core_v1_output(), "regime_base": "Transition", "regime_overlay": "None"}
        ro = RegimeOutput.from_core_v1_output(d)
        assert ro.traffic_light == "ORANGE"

    def test_regime_label_includes_overlay_when_present(self):
        d = {**_sample_core_v1_output(), "regime_overlay": "Recession-risk"}
        ro = RegimeOutput.from_core_v1_output(d)
        assert "Recession-risk" in ro.regime_label

    def test_confidence_preserved(self):
        ro = RegimeOutput.from_core_v1_output(_sample_core_v1_output())
        assert ro.confidence == 80

    def test_raw_preserved(self):
        d = _sample_core_v1_output()
        ro = RegimeOutput.from_core_v1_output(d)
        assert ro.raw["regime_base"] == "Goldilocks"


# ---------------------------------------------------------------------------
# PortfolioDiagnosticsPosition tests
# ---------------------------------------------------------------------------

class TestPortfolioDiagnosticsPosition:
    def test_to_dict(self):
        p = PortfolioDiagnosticsPosition(
            ticker="AAPL", weight_pct=0.2, macro_fit_score=80,
            color="green", optionality_consumed=False, tags=["regime_aligned"]
        )
        d = p.to_dict()
        assert d["ticker"] == "AAPL"
        assert d["macro_fit_score"] == 80
        assert d["tags"] == ["regime_aligned"]

    def test_from_dict(self):
        raw = {
            "ticker": "XOM", "weight_pct": 0.1, "macro_fit_score": 30,
            "color": "red", "optionality_consumed": True,
            "tags": ["regime_mismatch_cyclical"],
        }
        p = PortfolioDiagnosticsPosition.from_dict(raw)
        assert p.ticker == "XOM"
        assert p.optionality_consumed is True
        assert "regime_mismatch_cyclical" in p.tags

    def test_round_trip(self):
        raw = _sample_portfolio_state_dict()["positions"][0]
        p = PortfolioDiagnosticsPosition.from_dict(raw)
        result = p.to_dict()
        assert result["ticker"] == raw["ticker"]
        assert result["macro_fit_score"] == raw["macro_fit_score"]


# ---------------------------------------------------------------------------
# PortfolioSummary tests
# ---------------------------------------------------------------------------

class TestPortfolioSummary:
    def test_from_dict(self):
        d = _sample_portfolio_state_dict()["portfolio_summary"]
        s = PortfolioSummary.from_dict(d)
        assert s.total_positions == 3
        assert s.hhi == 0.12
        assert s.top_1_pct == 0.25

    def test_to_dict_round_trip(self):
        d = _sample_portfolio_state_dict()["portfolio_summary"]
        result = PortfolioSummary.from_dict(d).to_dict()
        assert result["total_positions"] == d["total_positions"]
        assert result["hhi"] == d["hhi"]


# ---------------------------------------------------------------------------
# PortfolioState tests
# ---------------------------------------------------------------------------

class TestPortfolioState:
    def test_from_dict(self):
        ps = PortfolioState.from_dict(_sample_portfolio_state_dict())
        assert ps.timestamp == _TIMESTAMP
        assert ps.portfolio_summary.total_positions == 3
        assert len(ps.positions) == 1
        assert isinstance(ps.positions[0], PortfolioDiagnosticsPosition)

    def test_to_dict_matches_input_structure(self):
        original = _sample_portfolio_state_dict()
        ps = PortfolioState.from_dict(original)
        d = ps.to_dict()
        assert d["timestamp"] == original["timestamp"]
        assert d["portfolio_summary"]["total_positions"] == 3
        assert d["exposures"]["by_sector"]["Technology"] == 0.35
        assert len(d["positions"]) == 1

    def test_risk_overlay_preserved_verbatim(self):
        """risk_overlay is an open dict — must survive round-trip unchanged."""
        original = _sample_portfolio_state_dict()
        ps = PortfolioState.from_dict(original)
        d = ps.to_dict()
        assert d["risk_overlay"]["macro_regime"]["traffic_light"] == "GREEN"
        assert d["risk_overlay"]["correlation_buckets"]["quality"] == 0.35

    def test_positions_are_typed(self):
        ps = PortfolioState.from_dict(_sample_portfolio_state_dict())
        for pos in ps.positions:
            assert isinstance(pos, PortfolioDiagnosticsPosition)


# ---------------------------------------------------------------------------
# Integration: normalize.py → PortfolioSnapshot round-trip
# ---------------------------------------------------------------------------

class TestNormalizeIntegration:
    """
    Verify that the dict returned by normalize_portfolio() can be parsed into
    a PortfolioSnapshot without errors. This validates that normalize.py and
    contracts.py stay in sync.
    """
    def test_normalize_output_is_snapshot_compatible(self, tmp_path):
        """normalize_portfolio() output must parse cleanly into PortfolioSnapshot."""
        import yaml
        import json
        from src.normalize import normalize_portfolio
        from src.paths import config_path, schema_path

        # Minimal instrument map
        inst_map = {"instrument_map": {1265: "AAPL", 2507: "TLT"}}
        inst_file = tmp_path / "etoro_instruments.yml"
        inst_file.write_text(yaml.dump(inst_map))

        assets = {"AAPL": {"asset_type": "Equity", "region": "US", "sector": "Technology"},
                  "TLT": {"asset_type": "ETF", "region": "US", "sector": "Government"}}
        assets_file = tmp_path / "assets.yml"
        assets_file.write_text(yaml.dump(assets))

        raw = {
            "clientPortfolio": {
                "credit": 100.0,
                "positions": [
                    {"instrumentID": 1265, "amount": 300.0},
                    {"instrumentID": 2507, "amount": 100.0},
                ],
            }
        }

        result_dict = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=str(inst_file),
            assets_config_path=str(assets_file),
        )

        # Must parse cleanly
        snapshot = PortfolioSnapshot.from_dict(result_dict)
        assert snapshot.currency == "USD"
        assert len(snapshot.positions) == 2
        tickers = {p.ticker for p in snapshot.positions}
        assert "AAPL" in tickers
        assert "TLT" in tickers

        # Round-trip must preserve structure
        reconstructed = snapshot.to_dict()
        assert reconstructed["cash_pct"] == result_dict["cash_pct"]
        assert len(reconstructed["positions"]) == 2


# ---------------------------------------------------------------------------
# ReportContext tests
# ---------------------------------------------------------------------------

def _sample_report_context(**overrides):
    base = dict(
        ts_str="20260315_100000",
        summary={"health_score": 95},
        alerts={"triggered": []},
        market_state=_sample_market_state_dict(),
        portfolio_state=_sample_portfolio_state_dict(),
        all_weather_alignment=None,
    )
    base.update(overrides)
    return ReportContext(**base)


class TestReportContext:
    def test_construction(self):
        ctx = _sample_report_context()
        assert ctx.ts_str == "20260315_100000"
        assert ctx.summary["health_score"] == 95
        assert ctx.market_state["risk_score"] == 72

    def test_has_alignment_data_false_when_none(self):
        ctx = _sample_report_context(all_weather_alignment=None)
        assert ctx.has_alignment_data() is False

    def test_has_alignment_data_false_when_empty(self):
        ctx = _sample_report_context(all_weather_alignment={})
        assert ctx.has_alignment_data() is False

    def test_has_alignment_data_true_when_present(self):
        ctx = _sample_report_context(all_weather_alignment={"brief_bullets": ["Posture: RISK_ON"]})
        assert ctx.has_alignment_data() is True

    def test_to_generate_markdown_args_returns_6_tuple(self):
        ctx = _sample_report_context()
        args = ctx.to_generate_markdown_args()
        assert len(args) == 6
        assert args[0] == ctx.ts_str
        assert args[1] == ctx.summary
        assert args[2] == ctx.alerts
        assert args[3] == ctx.market_state
        assert args[4] == ctx.portfolio_state
        assert args[5] is None  # all_weather_alignment

    def test_to_generate_markdown_args_passes_alignment(self):
        alignment = {"brief_bullets": ["something"]}
        ctx = _sample_report_context(all_weather_alignment=alignment)
        args = ctx.to_generate_markdown_args()
        assert args[5] is alignment

    def test_regime_output_bridge(self):
        """regime_output() must return a typed RegimeOutput from the embedded market_state."""
        ctx = _sample_report_context()
        ro = ctx.regime_output()
        assert isinstance(ro, RegimeOutput)
        assert ro.engine_id == "heuristic_v2"
        assert ro.risk_score == 72
        assert ro.traffic_light == "GREEN"

    def test_regime_output_reflects_market_state_color(self):
        ms = {**_sample_market_state_dict(), "color": "red", "risk_score": 25}
        ctx = _sample_report_context(market_state=ms)
        ro = ctx.regime_output()
        assert ro.traffic_light == "RED"
        assert ro.regime_label == "Risk-Off"

    def test_from_pipeline_outputs_constructor(self):
        ctx = ReportContext.from_pipeline_outputs(
            ts_str="20260315",
            summary={"health_score": 80},
            alerts={"triggered": []},
            market_state=_sample_market_state_dict(),
            portfolio_state=_sample_portfolio_state_dict(),
        )
        assert ctx.ts_str == "20260315"
        assert ctx.all_weather_alignment is None

    def test_from_pipeline_outputs_with_alignment(self):
        alignment = {"brief_bullets": ["RISK_ON"]}
        ctx = ReportContext.from_pipeline_outputs(
            ts_str="20260315",
            summary={"health_score": 80},
            alerts={"triggered": []},
            market_state=_sample_market_state_dict(),
            portfolio_state=_sample_portfolio_state_dict(),
            all_weather_alignment=alignment,
        )
        assert ctx.has_alignment_data() is True

    def test_from_pipeline_outputs_warns_on_missing_risk_score(self, caplog):
        import logging
        ms = dict(_sample_market_state_dict())
        del ms["risk_score"]  # simulate missing field
        with caplog.at_level(logging.WARNING, logger="src.contracts"):
            ReportContext.from_pipeline_outputs(
                ts_str="ts",
                summary={},
                alerts={},
                market_state=ms,
                portfolio_state=_sample_portfolio_state_dict(),
            )
        assert any("risk_score" in r.message for r in caplog.records)
