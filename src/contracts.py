"""
src/contracts.py — Lightweight shared data contracts for the core pipeline.

Design principles:
  - Pure Python dataclasses. No external runtime dependencies.
  - Each contract carries a to_dict() method that produces a plain dict compatible
    with the existing JSON schemas. All existing callers continue to work unchanged.
  - Each contract carries a from_dict() classmethod so any module can optionally
    consume typed inputs instead of raw dicts.
  - Fields are kept minimal and explicit. Optional fields use None defaults.
  - No business logic lives here — these are data containers only.

Contracts defined:
  - PortfolioPosition:    one position in a normalized snapshot
  - PortfolioSnapshot:    snapshot output of the provider/normalization layer
  - SubScore:             a single scored dimension (score 0-100, color label)
  - HeuristicMarketState: output of scoring/regime_model.py (V2 heuristic engine)
  - RegimeOutput:         unified future-facing contract that any regime engine can target
  - PortfolioDiagnosticsPosition: per-position output of portfolio_overlay
  - PortfolioSummary:     concentration summary from portfolio_overlay
  - PortfolioState:       aggregated portfolio state output
  - ReportContext:        typed input payload for publish/publish.py reporting layer
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _clean_dict(d: dict) -> dict:
    """Recursively removes None values from a dict (matches existing schema behaviour)."""
    result = {}
    for k, v in d.items():
        if v is None:
            continue
        if isinstance(v, dict):
            result[k] = _clean_dict(v)
        elif isinstance(v, list):
            result[k] = [_clean_dict(i) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


# ---------------------------------------------------------------------------
# Snapshot layer contracts
# ---------------------------------------------------------------------------

@dataclass
class PortfolioPosition:
    """
    One normalized position in a portfolio snapshot.

    Matches the 'items' shape of snapshot.schema.json > positions[].
    Optional fields (price, avg_open, pnl_pct) are present in the fixture but
    not required by the schema.
    """
    ticker: str
    asset_type: str
    region: str
    sector: str
    weight_pct: float
    price: Optional[float] = None
    avg_open: Optional[float] = None
    pnl_pct: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {
            "ticker": self.ticker,
            "asset_type": self.asset_type,
            "region": self.region,
            "sector": self.sector,
            "weight_pct": self.weight_pct,
        }
        if self.price is not None:
            d["price"] = self.price
        if self.avg_open is not None:
            d["avg_open"] = self.avg_open
        if self.pnl_pct is not None:
            d["pnl_pct"] = self.pnl_pct
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioPosition":
        return cls(
            ticker=d["ticker"],
            asset_type=d.get("asset_type", "Unknown"),
            region=d.get("region", "Unknown"),
            sector=d.get("sector", "Unknown"),
            weight_pct=float(d["weight_pct"]),
            price=d.get("price"),
            avg_open=d.get("avg_open"),
            pnl_pct=d.get("pnl_pct"),
        )


@dataclass
class PortfolioSnapshot:
    """
    Normalized portfolio snapshot. Output of the provider/normalization layer.

    Matches snapshot.schema.json.
    """
    date: str                           # ISO 8601 datetime string
    currency: str                       # e.g. "USD"
    cash_pct: float                     # 0.0 – 1.0
    positions: List[PortfolioPosition]  # ordered list of positions

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "currency": self.currency,
            "cash_pct": self.cash_pct,
            "positions": [p.to_dict() for p in self.positions],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioSnapshot":
        return cls(
            date=d["date"],
            currency=d.get("currency", "USD"),
            cash_pct=float(d["cash_pct"]),
            positions=[PortfolioPosition.from_dict(p) for p in d.get("positions", [])],
        )


# ---------------------------------------------------------------------------
# Macro / regime layer contracts
# ---------------------------------------------------------------------------

@dataclass
class SubScore:
    """
    One dimension of the heuristic regime scoring.
    score: 0-100 (100 = healthiest / most risk-on)
    color: "green" | "orange" | "red"
    """
    score: int
    color: str

    def to_dict(self) -> Dict[str, Any]:
        return {"score": self.score, "color": self.color}

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "SubScore":
        return cls(score=int(d["score"]), color=d["color"])


@dataclass
class HeuristicMarketState:
    """
    Output contract of scoring/regime_model.py (the V2 heuristic engine).

    Represents the market state produced from direct indicator scoring.
    Matches market_state.schema.json plus the additional fields that
    regime_model.py emits (sub_scores, regime_probabilities).

    This is NOT the same as the V5 macro-regime state (macro_regime_state.schema.json).
    The V5 state has its own fully-specified schema. This contract covers the V2 path.
    """
    timestamp: str                          # ISO 8601 datetime string
    risk_score: int                         # 0-100
    color: str                              # "green" | "orange" | "red"
    sub_scores: Dict[str, SubScore]         # keyed by dimension name
    regime_probabilities: Dict[str, float]  # e.g. recession_risk, policy_shock_risk
    indicators: Dict[str, Any]             # raw indicator dicts — intentionally open

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "risk_score": self.risk_score,
            "color": self.color,
            "sub_scores": {k: v.to_dict() for k, v in self.sub_scores.items()},
            "regime_probabilities": self.regime_probabilities,
            "indicators": self.indicators,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "HeuristicMarketState":
        raw_sub = d.get("sub_scores", {})
        sub_scores = {k: SubScore.from_dict(v) for k, v in raw_sub.items()}
        return cls(
            timestamp=d.get("timestamp", ""),
            risk_score=int(d.get("risk_score", 50)),
            color=d.get("color", "orange"),
            sub_scores=sub_scores,
            regime_probabilities=d.get("regime_probabilities", {}),
            indicators=d.get("indicators", {}),
        )


@dataclass
class RegimeOutput:
    """
    Unified future-facing contract that any regime engine should target.

    This is the normalized shape that the portfolio diagnostics layer
    and reporting layer should consume, regardless of which engine
    produced the underlying regime assessment.

    Current mapping:
      - HeuristicMarketState (V2): use RegimeOutput.from_heuristic_market_state()
      - core_v1_engine.py output: use RegimeOutput.from_core_v1_output()

    Both converters are additive — they do not change how the source engines work.

    Fields:
      engine_id:           which engine produced this output (for auditability)
      timestamp:           ISO 8601
      risk_score:          0-100 composite risk score (100 = full risk-on)
      traffic_light:       "GREEN" | "ORANGE" | "RED"
      regime_label:        human-readable label (e.g. "Goldilocks", "RISK_ON", "Stagflation")
      confidence:          0-100 confidence in the regime assessment
      p_drawdown_20:       probability of >20% drawdown (None if not computed)
      p_recession:         probability of recession (None if not computed)
      regime_probabilities: raw probability dict from V2 heuristic (optional)
      raw:                 the original engine output dict, preserved verbatim for downstream use
    """
    engine_id: str
    timestamp: str
    risk_score: int
    traffic_light: str                          # "GREEN" | "ORANGE" | "RED"
    regime_label: str                           # free-text label
    confidence: int                             # 0-100
    p_drawdown_20: Optional[float] = None
    p_recession: Optional[float] = None
    regime_probabilities: Dict[str, float] = field(default_factory=dict)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "engine_id": self.engine_id,
            "timestamp": self.timestamp,
            "risk_score": self.risk_score,
            "traffic_light": self.traffic_light,
            "regime_label": self.regime_label,
            "confidence": self.confidence,
            "regime_probabilities": self.regime_probabilities,
        }
        if self.p_drawdown_20 is not None:
            d["p_drawdown_20"] = self.p_drawdown_20
        if self.p_recession is not None:
            d["p_recession"] = self.p_recession
        return d

    @classmethod
    def from_heuristic_market_state(cls, d: Dict[str, Any]) -> "RegimeOutput":
        """
        Constructs a RegimeOutput from the dict produced by
        scoring.regime_model.evaluate_regimes_and_scores().

        Maps:
          risk_score → risk_score
          color      → traffic_light (green→GREEN, orange→ORANGE, red→RED)
          color      → regime_label (descriptive)
          regime_probabilities.recession_risk → p_recession
        """
        color = d.get("color", "orange")
        traffic_light = color.upper()
        color_to_label = {
            "green": "Risk-On",
            "orange": "Neutral",
            "red": "Risk-Off",
        }
        regime_probs = d.get("regime_probabilities", {})
        return cls(
            engine_id="heuristic_v2",
            timestamp=d.get("timestamp", ""),
            risk_score=int(d.get("risk_score", 50)),
            traffic_light=traffic_light,
            regime_label=color_to_label.get(color, "Neutral"),
            confidence=50,  # V2 heuristic has no explicit confidence score
            p_drawdown_20=None,  # V2 does not compute drawdown probabilities
            p_recession=regime_probs.get("recession_risk"),
            regime_probabilities=regime_probs,
            raw=d,
        )

    @classmethod
    def from_core_v1_output(cls, d: Dict[str, Any]) -> "RegimeOutput":
        """
        Constructs a RegimeOutput from the dict produced by
        macro_regime.core_v1_engine.CoreMacroRegimeEngineV1.evaluate().

        Maps:
          regime_base + regime_overlay → regime_label
          confidence                   → confidence
          (no risk_score or traffic_light in V1 — approximated)
        """
        base = d.get("regime_base", "Transition")
        overlay = d.get("regime_overlay", "None")
        regime_label = base if overlay == "None" else f"{base} / {overlay}"
        conf = int(d.get("confidence", 50))

        # Approximate traffic light from base quadrant
        bullish = {"Goldilocks", "Reflation"}
        bearish = {"Stagflation"}
        if base in bullish and overlay != "Recession-risk":
            traffic_light = "GREEN"
            risk_score = 70
        elif base in bearish or overlay == "Recession-risk":
            traffic_light = "RED"
            risk_score = 25
        else:
            traffic_light = "ORANGE"
            risk_score = 50

        return cls(
            engine_id="core_v1",
            timestamp=d.get("timestamp_utc", ""),
            risk_score=risk_score,
            traffic_light=traffic_light,
            regime_label=regime_label,
            confidence=conf,
            p_drawdown_20=None,
            p_recession=None,
            regime_probabilities={},
            raw=d,
        )


# ---------------------------------------------------------------------------
# Portfolio diagnostics layer contracts
# ---------------------------------------------------------------------------

@dataclass
class PortfolioDiagnosticsPosition:
    """
    Per-position output from the portfolio overlay / diagnostics layer.
    Matches portfolio_state.schema.json > positions[].
    """
    ticker: str
    weight_pct: float
    macro_fit_score: int        # 0-100
    color: str                  # "green" | "orange" | "red"
    optionality_consumed: bool
    tags: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ticker": self.ticker,
            "weight_pct": self.weight_pct,
            "macro_fit_score": self.macro_fit_score,
            "color": self.color,
            "optionality_consumed": self.optionality_consumed,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioDiagnosticsPosition":
        return cls(
            ticker=d["ticker"],
            weight_pct=float(d["weight_pct"]),
            macro_fit_score=int(d.get("macro_fit_score", 50)),
            color=d.get("color", "orange"),
            optionality_consumed=bool(d.get("optionality_consumed", False)),
            tags=list(d.get("tags", [])),
        )


@dataclass
class PortfolioSummary:
    """
    Concentration summary from the portfolio overlay.
    Matches portfolio_state.schema.json > portfolio_summary.
    """
    total_positions: int
    cash_pct: float
    hhi: float
    top_1_pct: float
    top_4_pct: float
    top_10_pct: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_positions": self.total_positions,
            "cash_pct": self.cash_pct,
            "hhi": self.hhi,
            "top_1_pct": self.top_1_pct,
            "top_4_pct": self.top_4_pct,
            "top_10_pct": self.top_10_pct,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioSummary":
        return cls(
            total_positions=int(d.get("total_positions", 0)),
            cash_pct=float(d.get("cash_pct", 0.0)),
            hhi=float(d.get("hhi", 0.0)),
            top_1_pct=float(d.get("top_1_pct", 0.0)),
            top_4_pct=float(d.get("top_4_pct", 0.0)),
            top_10_pct=float(d.get("top_10_pct", 0.0)),
        )


@dataclass
class PortfolioState:
    """
    Full portfolio diagnostics state. Output of portfolio/portfolio_overlay.py.
    Matches portfolio_state.schema.json.

    The raw dict form is kept as the primary pipeline output for now — this
    contract is used for typed access within modules that consume portfolio_state.
    """
    timestamp: str
    portfolio_summary: PortfolioSummary
    exposures: Dict[str, Any]       # by_sector, by_region, by_asset_type — open dict
    risk_overlay: Dict[str, Any]    # macro_regime, correlation_buckets, flags — open dict
    positions: List[PortfolioDiagnosticsPosition]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "portfolio_summary": self.portfolio_summary.to_dict(),
            "exposures": self.exposures,
            "risk_overlay": self.risk_overlay,
            "positions": [p.to_dict() for p in self.positions],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PortfolioState":
        return cls(
            timestamp=d.get("timestamp", ""),
            portfolio_summary=PortfolioSummary.from_dict(d.get("portfolio_summary", {})),
            exposures=d.get("exposures", {}),
            risk_overlay=d.get("risk_overlay", {}),
            positions=[
                PortfolioDiagnosticsPosition.from_dict(p)
                for p in d.get("positions", [])
            ],
        )


# ---------------------------------------------------------------------------
# Reporting layer contracts
# ---------------------------------------------------------------------------

@dataclass
class ReportContext:
    """
    Typed input payload for the reporting layer (publish/publish.py).

    Formalizes the 5 loose dict arguments of generate_markdown_report() into
    a single inspectable struct. This makes it easy to:
      - see what data the report depends on at a glance
      - validate that all required inputs are present before calling the reporter
      - swap or mock individual inputs in tests

    Matching the current signature of publish.generate_markdown_report():
      ts_str, summary, alerts, market_state, portfolio_state, all_weather_alignment=None

    Usage (non-breaking, callers can keep using dict args directly):
      ctx = ReportContext.from_pipeline_outputs(...)
      generate_markdown_report(*ctx.to_generate_markdown_args())
    """
    ts_str: str                             # timestamp string used for file naming
    summary: Dict[str, Any]                # health score summary dict
    alerts: Dict[str, Any]                 # evaluated alert rules dict
    market_state: Dict[str, Any]           # output of scoring.regime_model (V2 heuristic)
    portfolio_state: Dict[str, Any]        # output of portfolio.portfolio_overlay
    all_weather_alignment: Optional[Dict[str, Any]] = None  # optional alignment output

    def to_generate_markdown_args(self):
        """
        Returns the positional args to pass directly to
        publish.generate_markdown_report(). Convenience for typed callers.
        """
        return (
            self.ts_str,
            self.summary,
            self.alerts,
            self.market_state,
            self.portfolio_state,
            self.all_weather_alignment,
        )

    @classmethod
    def from_pipeline_outputs(
        cls,
        ts_str: str,
        summary: Dict[str, Any],
        alerts: Dict[str, Any],
        market_state: Dict[str, Any],
        portfolio_state: Dict[str, Any],
        all_weather_alignment: Optional[Dict[str, Any]] = None,
    ) -> "ReportContext":
        """
        Constructs a ReportContext from named pipeline step outputs.
        Logs warnings for common missing fields without raising.
        """
        if market_state and market_state.get("risk_score") is None:
            logger.warning("ReportContext: market_state missing 'risk_score' field.")
        if portfolio_state and not portfolio_state.get("portfolio_summary"):
            logger.warning("ReportContext: portfolio_state missing 'portfolio_summary' field.")
        return cls(
            ts_str=ts_str,
            summary=summary,
            alerts=alerts,
            market_state=market_state,
            portfolio_state=portfolio_state,
            all_weather_alignment=all_weather_alignment,
        )

    def has_alignment_data(self) -> bool:
        """Returns True if all_weather_alignment data is present and non-empty."""
        return bool(self.all_weather_alignment)

    def regime_output(self) -> "RegimeOutput":
        """
        Convenience: wraps the embedded market_state into a typed RegimeOutput.
        This is the bridge between V2 heuristic engine output and the unified contract.
        """
        return RegimeOutput.from_heuristic_market_state(self.market_state)
