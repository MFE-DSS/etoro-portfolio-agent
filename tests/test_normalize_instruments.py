"""
tests/test_normalize_instruments.py

Tests for the instrument mapping extraction and normalize_portfolio() refactor.

Coverage:
  - load_instrument_map(): happy path, missing file, malformed file
  - resolve_ticker(): known instrument, unknown instrument (warning + UNMAPPED_ prefix)
  - normalize_portfolio(): end-to-end with known instruments, unknown instruments,
    empty portfolio, all-cash portfolio
  - src/paths.py: ROOT_DIR resolution sanity check
"""

import json
import logging
import os
import tempfile

import pytest
import yaml

from src.normalize import (
    load_instrument_map,
    load_assets_config,
    resolve_ticker,
    normalize_portfolio,
)
from src.paths import ROOT_DIR, config_path, schema_path


# ---------------------------------------------------------------------------
# Helpers / Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def minimal_instrument_map_file(tmp_path):
    """Writes a temporary etoro_instruments.yml with two known instruments."""
    data = {
        "instrument_map": {
            1265: "AAPL",
            2507: "TLT",
        }
    }
    p = tmp_path / "etoro_instruments.yml"
    p.write_text(yaml.dump(data))
    return str(p)


@pytest.fixture
def minimal_assets_config_file(tmp_path):
    """Writes a temporary assets.yml with metadata for AAPL and TLT."""
    data = {
        "AAPL": {
            "asset_type": "Equity",
            "region": "US",
            "sector": "Technology",
        },
        "TLT": {
            "asset_type": "ETF",
            "region": "US",
            "sector": "Government",
        },
    }
    p = tmp_path / "assets.yml"
    p.write_text(yaml.dump(data))
    return str(p)


def _make_raw_payload(positions: list, credit: float = 0.0) -> dict:
    """Helper to construct a minimal eToro raw API payload."""
    return {
        "clientPortfolio": {
            "credit": credit,
            "positions": positions,
        }
    }


def _make_position(instrument_id: int, amount: float) -> dict:
    return {"instrumentID": instrument_id, "amount": amount}


# ---------------------------------------------------------------------------
# A. src/paths.py tests
# ---------------------------------------------------------------------------

class TestPaths:
    def test_root_dir_exists(self):
        """ROOT_DIR must point to an existing directory containing config/."""
        assert ROOT_DIR.is_dir(), f"ROOT_DIR {ROOT_DIR} is not a directory"
        assert (ROOT_DIR / "config").is_dir(), "ROOT_DIR should have a config/ subdirectory"

    def test_config_path_returns_correct_absolute_path(self):
        p = config_path("assets.yml")
        assert p.is_absolute()
        assert p.name == "assets.yml"
        assert "config" in str(p)

    def test_schema_path_returns_correct_absolute_path(self):
        p = schema_path("snapshot.schema.json")
        assert p.is_absolute()
        assert p.name == "snapshot.schema.json"
        assert "schemas" in str(p)

    def test_config_path_resolves_etoro_instruments(self):
        """The newly created etoro_instruments.yml must be reachable via config_path()."""
        p = config_path("etoro_instruments.yml")
        assert p.exists(), (
            f"config/etoro_instruments.yml not found at {p}. "
            "Ensure it was created during this story."
        )


# ---------------------------------------------------------------------------
# B. load_instrument_map() tests
# ---------------------------------------------------------------------------

class TestLoadInstrumentMap:
    def test_happy_path_loads_known_instruments(self, minimal_instrument_map_file):
        mapping = load_instrument_map(minimal_instrument_map_file)
        assert mapping == {1265: "AAPL", 2507: "TLT"}

    def test_keys_are_integers(self, minimal_instrument_map_file):
        mapping = load_instrument_map(minimal_instrument_map_file)
        for k in mapping:
            assert isinstance(k, int), f"Expected int key, got {type(k)}"

    def test_values_are_strings(self, minimal_instrument_map_file):
        mapping = load_instrument_map(minimal_instrument_map_file)
        for v in mapping.values():
            assert isinstance(v, str), f"Expected str value, got {type(v)}"

    def test_missing_file_returns_empty_dict_not_raises(self, tmp_path):
        """A missing config file must not crash the normalizer."""
        missing = str(tmp_path / "nonexistent.yml")
        mapping = load_instrument_map(missing)
        assert mapping == {}

    def test_missing_file_logs_error(self, tmp_path, caplog):
        missing = str(tmp_path / "nonexistent.yml")
        with caplog.at_level(logging.ERROR, logger="src.normalize"):
            load_instrument_map(missing)
        assert any("not found" in r.message.lower() or "etoro_instruments" in r.message for r in caplog.records)

    def test_empty_yaml_file_returns_empty_dict(self, tmp_path):
        p = tmp_path / "etoro_instruments.yml"
        p.write_text("")  # empty file
        mapping = load_instrument_map(str(p))
        assert mapping == {}

    def test_yaml_without_instrument_map_key_returns_empty_dict(self, tmp_path):
        """YAML that exists but lacks the 'instrument_map' key should return {}."""
        p = tmp_path / "etoro_instruments.yml"
        p.write_text(yaml.dump({"something_else": {1: "X"}}))
        mapping = load_instrument_map(str(p))
        assert mapping == {}

    def test_real_config_loads_all_8_instruments(self):
        """The actual config/etoro_instruments.yml must load 8 instruments."""
        p = config_path("etoro_instruments.yml")
        mapping = load_instrument_map(str(p))
        assert len(mapping) == 8, (
            f"Expected 8 instruments in etoro_instruments.yml, got {len(mapping)}"
        )


# ---------------------------------------------------------------------------
# C. resolve_ticker() tests
# ---------------------------------------------------------------------------

class TestResolveTicker:
    SAMPLE_MAP = {1265: "AAPL", 2507: "TLT", 10579: "BTC"}

    def test_known_instrument_returns_ticker(self):
        assert resolve_ticker(1265, self.SAMPLE_MAP) == "AAPL"
        assert resolve_ticker(2507, self.SAMPLE_MAP) == "TLT"
        assert resolve_ticker(10579, self.SAMPLE_MAP) == "BTC"

    def test_unknown_instrument_returns_unmapped_prefix(self):
        result = resolve_ticker(99999, self.SAMPLE_MAP)
        assert result == "UNMAPPED_99999"

    def test_unknown_instrument_does_not_raise(self):
        """Unknown instrument must never raise — it must return a safe value."""
        result = resolve_ticker(0, self.SAMPLE_MAP)
        assert result.startswith("UNMAPPED_")

    def test_unknown_instrument_logs_warning(self, caplog):
        with caplog.at_level(logging.WARNING, logger="src.normalize"):
            resolve_ticker(55555, self.SAMPLE_MAP)
        assert any("55555" in r.message and ("UNMAPPED" in r.message or "not present" in r.message.lower())
                   for r in caplog.records)

    def test_unmapped_ticker_format_is_stable(self):
        """The UNMAPPED_ prefix format must be exactly UNMAPPED_<id> — not ASSET_<id>."""
        result = resolve_ticker(12345, {})
        assert result == "UNMAPPED_12345"
        # Explicitly ensure the old format is gone
        assert "ASSET_" not in result

    def test_empty_map_always_returns_unmapped(self):
        for inst_id in [1, 100, 9999]:
            assert resolve_ticker(inst_id, {}) == f"UNMAPPED_{inst_id}"


# ---------------------------------------------------------------------------
# D. normalize_portfolio() end-to-end tests
# ---------------------------------------------------------------------------

class TestNormalizePortfolio:

    def test_known_instruments_produce_correct_tickers(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        raw = _make_raw_payload([
            _make_position(1265, 200.0),  # AAPL
            _make_position(2507, 100.0),  # TLT
        ], credit=100.0)  # total equity = 400

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        tickers = {p["ticker"] for p in snapshot["positions"]}
        assert "AAPL" in tickers
        assert "TLT" in tickers
        assert all(not t.startswith("UNMAPPED_") for t in tickers)

    def test_unknown_instruments_produce_unmapped_tickers(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """Position with unknown instrumentID must appear as UNMAPPED_<id>, not silently dropped."""
        unknown_id = 99999
        raw = _make_raw_payload([
            _make_position(1265, 100.0),    # AAPL — known
            _make_position(unknown_id, 100.0),  # unknown
        ])

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        tickers = {p["ticker"] for p in snapshot["positions"]}
        assert f"UNMAPPED_{unknown_id}" in tickers, (
            "Unknown instrument must appear as UNMAPPED_<id> in output, not be silently dropped"
        )

    def test_unknown_instrument_logs_warning_in_normalize(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path, caplog
    ):
        raw = _make_raw_payload([_make_position(77777, 100.0)])
        with caplog.at_level(logging.WARNING, logger="src.normalize"):
            normalize_portfolio(
                raw,
                out_dir=str(tmp_path),
                instrument_map_path=minimal_instrument_map_file,
                assets_config_path=minimal_assets_config_file,
            )
        assert any("77777" in r.message for r in caplog.records)

    def test_weight_accounting_includes_unmapped_positions(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """Unmapped positions must still contribute to weight calculations."""
        raw = _make_raw_payload([
            _make_position(1265, 100.0),    # AAPL
            _make_position(88888, 100.0),   # unknown
        ])  # total_invested=200, credit=0, total_equity=200

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        total_weight = sum(p["weight_pct"] for p in snapshot["positions"])
        # weights should sum to ~1.0 (all invested, no cash)
        assert abs(total_weight - 1.0) < 0.01, (
            f"Weights should sum to ~1.0, got {total_weight}"
        )

    def test_cash_pct_is_correct(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        raw = _make_raw_payload([
            _make_position(1265, 300.0),
        ], credit=100.0)  # total equity = 400, cash = 100/400 = 0.25

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        assert abs(snapshot["cash_pct"] - 0.25) < 0.001

    def test_all_cash_portfolio(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """Portfolio with no positions should have cash_pct=1.0 and empty positions list."""
        raw = _make_raw_payload([], credit=1000.0)

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        assert snapshot["cash_pct"] == 1.0
        assert snapshot["positions"] == []

    def test_zero_equity_portfolio(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """Portfolio with no positions and no credit should not raise."""
        raw = _make_raw_payload([], credit=0.0)

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        assert snapshot["cash_pct"] == 1.0  # defined safe fallback
        assert snapshot["positions"] == []

    def test_snapshot_validates_against_schema(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """The snapshot produced by normalize_portfolio must be valid against snapshot.schema.json."""
        raw = _make_raw_payload([
            _make_position(1265, 200.0),
            _make_position(2507, 100.0),
            _make_position(99999, 50.0),  # UNMAPPED — must still validate
        ], credit=50.0)

        # Should not raise jsonschema.exceptions.ValidationError
        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        assert "positions" in snapshot
        assert "cash_pct" in snapshot
        assert "currency" in snapshot
        assert "date" in snapshot

    def test_metadata_enrichment_for_known_assets(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        raw = _make_raw_payload([_make_position(1265, 100.0)])

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        aapl = next(p for p in snapshot["positions"] if p["ticker"] == "AAPL")
        assert aapl["asset_type"] == "Equity"
        assert aapl["region"] == "US"
        assert aapl["sector"] == "Technology"

    def test_unmapped_assets_get_unknown_metadata(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        raw = _make_raw_payload([_make_position(99999, 100.0)])

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        unmapped = next(p for p in snapshot["positions"] if p["ticker"].startswith("UNMAPPED_"))
        assert unmapped["asset_type"] == "Unknown"
        assert unmapped["region"] == "Unknown"
        assert unmapped["sector"] == "Unknown"

    def test_multiple_positions_same_instrument_are_grouped(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        """Two entries with the same instrumentID must be merged into one position."""
        raw = _make_raw_payload([
            _make_position(1265, 100.0),
            _make_position(1265, 50.0),  # same instrument, additional lot
        ])

        snapshot = normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        aapl_positions = [p for p in snapshot["positions"] if p["ticker"] == "AAPL"]
        assert len(aapl_positions) == 1, "Multiple lots of same instrument must be merged into one position"
        assert abs(aapl_positions[0]["weight_pct"] - 1.0) < 0.001

    def test_artifact_is_written_to_out_dir(
        self, minimal_instrument_map_file, minimal_assets_config_file, tmp_path
    ):
        raw = _make_raw_payload([_make_position(1265, 100.0)])

        normalize_portfolio(
            raw,
            out_dir=str(tmp_path),
            instrument_map_path=minimal_instrument_map_file,
            assets_config_path=minimal_assets_config_file,
        )

        written_files = list(tmp_path.glob("snapshot_*.json"))
        assert len(written_files) == 1, "normalize_portfolio must write exactly one snapshot_*.json artifact"
