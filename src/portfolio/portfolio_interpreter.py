"""
portfolio_interpreter.py — Deterministic portfolio interpretation layer.

Takes the normalized snapshot + enriched portfolio_state + market_state and
produces a structured, human-readable interpretation object used by the email
report generator.

No LLM calls. No external I/O. Pure deterministic logic.
"""

from typing import Dict, Any, List


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def interpret_portfolio(
    snapshot: Dict[str, Any],
    portfolio_state: Dict[str, Any],
    market_state: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Build the portfolio interpretation layer.

    Returns a dict with:
      n_positions, cash_pct, top5_by_weight, concentration,
      by_factor, by_sector, by_region, by_asset_type,
      missing_sleeves, regime_contradictions, regime_protections,
      posture_label, narrative_summary
    """
    snap_positions = snapshot.get("positions", [])
    ps_positions = portfolio_state.get("positions", [])  # enriched, macro-scored
    summary = portfolio_state.get("portfolio_summary", {})
    exposures = portfolio_state.get("exposures", {})
    buckets = portfolio_state.get("risk_overlay", {}).get("correlation_buckets", {})
    regime_color = market_state.get("color", "orange")

    # Build lookup: ticker → ps position (has color, tags, macro_fit_score)
    ps_lookup: Dict[str, Dict] = {p["ticker"]: p for p in ps_positions}

    # 1. Top-5 positions by weight
    sorted_pos = sorted(snap_positions, key=lambda p: p.get("weight_pct", 0.0), reverse=True)
    top5 = []
    for p in sorted_pos[:5]:
        ticker = p.get("ticker", "?")
        ps = ps_lookup.get(ticker, {})
        pnl = p.get("pnl_pct")
        top5.append({
            "ticker": ticker,
            "weight_pct": round(p.get("weight_pct", 0.0) * 100, 1),
            "sector": p.get("sector", "Unknown"),
            "asset_type": p.get("asset_type", "Unknown"),
            "pnl_pct": round(pnl * 100, 1) if pnl is not None else None,
            "macro_fit": ps.get("color", "unknown"),
        })

    # 2. Concentration
    hhi = summary.get("hhi", 0.0)
    top1 = summary.get("top_1_pct", 0.0)
    top4 = summary.get("top_4_pct", 0.0)

    if hhi > 0.25 or top4 > 0.65:
        conc_warning = "HIGH"
    elif hhi > 0.15 or top4 > 0.50:
        conc_warning = "MODERATE"
    else:
        conc_warning = "OK"

    # 3. Factor breakdown (percent of total portfolio)
    factor_pct: Dict[str, float] = {
        k: round(v * 100, 1)
        for k, v in sorted(buckets.items(), key=lambda x: -x[1])
        if v > 0.001
    }

    # 4. Sector / region / asset-type breakdowns
    def pct_dict(raw: Dict[str, float]) -> Dict[str, float]:
        return {
            k: round(v * 100, 1)
            for k, v in sorted(raw.items(), key=lambda x: -x[1])
            if v > 0.001
        }

    sector_pct = pct_dict(exposures.get("by_sector", {}))
    region_pct = pct_dict(exposures.get("by_region", {}))
    asset_type_pct = pct_dict(exposures.get("by_asset_type", {}))

    # 5. Cash
    cash_pct = round(snapshot.get("cash_pct", 0.0) * 100, 1)

    # 6. Missing sleeves
    missing_sleeves = _detect_missing_sleeves(snap_positions, buckets, regime_color, cash_pct)

    # 7. Regime contradictions and protections
    contradictions, protections = _assess_regime_fit(ps_positions)

    # 8. Overlap / redundancy: same factor_bucket, same region, both overweight
    redundant_pairs = _detect_redundant_pairs(snap_positions, buckets)

    # 9. Overall posture label
    red_weight = sum(
        p.get("weight_pct", 0.0) for p in ps_positions if p.get("color") == "red"
    )
    posture_label = _compute_posture_label(red_weight, missing_sleeves)

    # 10. Narrative summary
    narrative = _build_narrative(
        n_positions=len(snap_positions),
        cash_pct=cash_pct,
        conc_warning=conc_warning,
        hhi=hhi,
        missing_sleeves=missing_sleeves,
        posture_label=posture_label,
        regime_color=regime_color,
    )

    return {
        "n_positions": len(snap_positions),
        "cash_pct": cash_pct,
        "top5_by_weight": top5,
        "concentration": {
            "hhi": round(hhi, 4),
            "top1_pct": round(top1 * 100, 1),
            "top4_pct": round(top4 * 100, 1),
            "warning": conc_warning,
        },
        "by_factor": factor_pct,
        "by_sector": sector_pct,
        "by_region": region_pct,
        "by_asset_type": asset_type_pct,
        "missing_sleeves": missing_sleeves,
        "redundant_pairs": redundant_pairs,
        "regime_contradictions": contradictions[:5],
        "regime_protections": protections[:5],
        "posture_label": posture_label,
        "narrative_summary": narrative,
    }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_GOLD_TICKERS = {"GLD", "IAU", "GOLD", "SGOL", "PHYS", "BAR"}
_BOND_TICKERS = {"TLT", "IEF", "SHY", "AGG", "BND", "VGIT", "GOVT", "EDV"}
_REIT_TICKERS = {"VNQ", "SCHH", "RWR", "IYR", "XLRE"}
_TIPS_TICKERS = {"TIP", "STIP", "SCHP", "VTIP"}


def _detect_missing_sleeves(
    positions: List[Dict],
    buckets: Dict[str, float],
    regime_color: str,
    cash_pct: float,
) -> List[Dict[str, str]]:
    """Return a list of missing diversification sleeves with explanatory notes."""
    missing = []

    # --- Bond / Duration sleeve ---
    rates_weight = buckets.get("rates_sensitive", 0.0)
    bond_tickers_held = {p["ticker"] for p in positions if p.get("ticker") in _BOND_TICKERS}
    if rates_weight < 0.05 and not bond_tickers_held:
        missing.append({
            "sleeve": "Duration / Bonds",
            "note": (
                "No meaningful bond exposure detected. Long-duration Treasuries (e.g. TLT) "
                "act as portfolio ballast and tend to rally in risk-off / recession regimes."
            ),
        })

    # --- Gold / Inflation-hedge sleeve ---
    gold_weight = sum(
        p.get("weight_pct", 0.0)
        for p in positions
        if p.get("ticker") in _GOLD_TICKERS or p.get("sector") == "Basic Materials"
    )
    if gold_weight < 0.05:
        missing.append({
            "sleeve": "Gold / Inflation Hedge",
            "note": (
                "No meaningful gold or precious metals exposure. Gold provides an inflation "
                "hedge, crisis buffer, and low-correlation diversification across all regimes."
            ),
        })

    # --- Defensive equity sleeve (only warn in non risk-on environments) ---
    defensives_weight = buckets.get("defensives", 0.0)
    if defensives_weight < 0.05 and regime_color != "green":
        missing.append({
            "sleeve": "Defensive Equities",
            "note": (
                "Defensive equity weight is below 5% in a non risk-on regime. Healthcare, "
                "utilities, and consumer staples tend to be more resilient in downturns."
            ),
        })

    # --- Real assets / REIT sleeve (optional, only flag in inflationary regime) ---
    reit_weight = sum(
        p.get("weight_pct", 0.0)
        for p in positions
        if p.get("ticker") in _REIT_TICKERS
    )
    if reit_weight < 0.03 and buckets.get("energy", 0.0) < 0.05:
        missing.append({
            "sleeve": "Real Assets (REIT / Energy)",
            "note": (
                "No significant real-asset or energy exposure. These tend to act as "
                "inflation buffers and diversify away from pure financial-asset risk."
            ),
        })

    # --- Geographic diversification warning ---
    us_equity_weight = sum(
        p.get("weight_pct", 0.0)
        for p in positions
        if p.get("region") == "US" and p.get("asset_type") in {"Equity", "ETF"}
    )
    if us_equity_weight > 0.55:
        missing.append({
            "sleeve": "Geographic Diversification",
            "note": (
                f"US-centric equity exposure is {us_equity_weight * 100:.0f}% of portfolio. "
                "Consider adding international developed (e.g. EFA) or EM (e.g. EEM) exposure."
            ),
        })

    # --- Excess cash warning (>30%) ---
    if cash_pct > 30.0:
        missing.append({
            "sleeve": "Cash Deployment",
            "note": (
                f"Cash is {cash_pct:.0f}% of portfolio — potentially excess dry powder. "
                "Evaluate whether this is intentional or an under-deployment of capital."
            ),
        })

    return missing


def _assess_regime_fit(
    ps_positions: List[Dict],
) -> tuple:
    """Split positions into regime contradictions and regime protections."""
    contradictions = []
    protections = []

    for p in ps_positions:
        ticker = p.get("ticker", "?")
        color = p.get("color", "orange")
        tags = p.get("tags", [])
        weight = p.get("weight_pct", 0.0)

        if weight < 0.03:
            continue  # ignore noise positions

        if color == "red":
            reason = next(
                (t.replace("_", " ") for t in tags if "mismatch" in t or "headwind" in t or "overweight" in t),
                "regime mismatch",
            )
            contradictions.append({
                "ticker": ticker,
                "weight_pct": round(weight * 100, 1),
                "reason": reason,
            })
        elif color == "green":
            reason = next(
                (t.replace("_", " ") for t in tags if "aligned" in t),
                "regime aligned",
            )
            protections.append({
                "ticker": ticker,
                "weight_pct": round(weight * 100, 1),
                "reason": reason,
            })

    # Sort by weight descending
    contradictions.sort(key=lambda x: -x["weight_pct"])
    protections.sort(key=lambda x: -x["weight_pct"])
    return contradictions, protections


def _detect_redundant_pairs(
    positions: List[Dict],
    buckets: Dict[str, float],
) -> List[Dict[str, str]]:
    """
    Flag potential redundancy: multiple large positions in the same sector + region.
    Only flags pairs where combined weight > 20% and sector is the same.
    """
    from collections import defaultdict

    sector_group: Dict[str, List] = defaultdict(list)
    for p in positions:
        key = f"{p.get('sector', 'Unknown')}|{p.get('region', 'Unknown')}"
        sector_group[key].append(p)

    pairs = []
    for key, group in sector_group.items():
        if len(group) < 2:
            continue
        combined = sum(p.get("weight_pct", 0.0) for p in group)
        if combined > 0.20:
            tickers = [p["ticker"] for p in sorted(group, key=lambda x: -x.get("weight_pct", 0.0))]
            sector, region = key.split("|")
            pairs.append({
                "tickers": tickers,
                "sector": sector,
                "region": region,
                "combined_weight_pct": round(combined * 100, 1),
                "note": (
                    f"Multiple positions in {sector} / {region} combine to "
                    f"{combined * 100:.0f}% — consider whether these are genuinely "
                    "complementary or effectively the same exposure."
                ),
            })

    return pairs[:3]  # cap at 3


def _compute_posture_label(red_weight: float, missing_sleeves: List) -> str:
    """Summarise overall alignment vs current regime."""
    n_missing = len(missing_sleeves)
    if red_weight > 0.35 or n_missing >= 4:
        return "MISALIGNED"
    if red_weight > 0.15 or n_missing >= 2:
        return "PARTIALLY_ALIGNED"
    return "ALIGNED"


def _build_narrative(
    n_positions: int,
    cash_pct: float,
    conc_warning: str,
    hhi: float,
    missing_sleeves: List,
    posture_label: str,
    regime_color: str,
) -> str:
    regime_word = {
        "green": "risk-on",
        "orange": "transitional",
        "red": "risk-off",
    }.get(regime_color, "mixed")

    parts = [
        f"{n_positions} positions, {cash_pct:.0f}% cash.",
        f"Concentration is {conc_warning.lower()} (HHI {hhi:.3f}).",
    ]

    if missing_sleeves:
        names = [s["sleeve"] for s in missing_sleeves[:2]]
        suffix = f" (+{len(missing_sleeves) - 2} more)" if len(missing_sleeves) > 2 else ""
        parts.append(f"Missing diversification: {', '.join(names)}{suffix}.")

    posture_text = posture_label.replace("_", " ").lower()
    parts.append(
        f"In the current {regime_word} regime, portfolio appears {posture_text}."
    )

    return " ".join(parts)
