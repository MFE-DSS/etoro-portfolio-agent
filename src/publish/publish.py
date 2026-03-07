"""
publish.py — Report generation and artifact packaging.

generate_markdown_report() produces a 7-section operator dashboard email:
  1. Executive Summary
  2. Current Macro Regime
  3. Portfolio Snapshot
  4. Regime Alignment Assessment
  5. Risks & Concentration Warnings
  6. Watchpoints & Rebalance Considerations
  7. Machine-Readable Appendix

Sections degrade gracefully when inputs are partial or missing.
"""

import os
import json
import shutil
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Artifact packaging
# ---------------------------------------------------------------------------

def zip_run_bundle(bundle_dir: str) -> str:
    """Zips the nested bundle directory for easy transport."""
    archive_path = shutil.make_archive(bundle_dir, "zip", bundle_dir)
    return archive_path


def optional_google_drive_upload(zip_path: str):
    """Stubbed Drive uploader behind a strict opt-in env flag."""
    if os.environ.get("ENABLE_GDRIVE_UPLOAD") == "true":
        logger.info(f"ENABLE_GDRIVE_UPLOAD=true. [Dry Run] Would upload {zip_path} to Google Drive.")
    else:
        logger.debug("Google Drive upload disabled.")


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _pct(val, scale=1.0, dec=0) -> str:
    """Format a float as a percentage string. scale=100 if val is 0-1."""
    if val is None:
        return "n/a"
    return f"{float(val) * scale:.{dec}f}%"


def _num(val, dec=2) -> str:
    if val is None:
        return "n/a"
    return f"{float(val):.{dec}f}"


def _band(val, low=0.15, high=0.35) -> str:
    """Return Low / Moderate / High label for a probability."""
    if val is None:
        return "n/a"
    if val <= low:
        return f"{val * 100:.0f}% — Low"
    if val <= high:
        return f"{val * 100:.0f}% — Moderate"
    return f"{val * 100:.0f}% — High"


def _bar(val_pct: float, width: int = 20) -> str:
    """Simple ASCII bar for a percentage (0-100)."""
    filled = max(0, min(width, int(val_pct / 100 * width)))
    return "█" * filled + "░" * (width - filled)


# ---------------------------------------------------------------------------
# Section builders
# ---------------------------------------------------------------------------

def _section_executive_summary(
    ts_str: str,
    asof_date: str,
    posture: str,
    confidence: str,
    health_score: int,
    health_color: str,
    regime_label: str,
    interpretation: Optional[Dict],
) -> str:
    port_posture = ""
    if interpretation:
        pl = interpretation.get("posture_label", "UNKNOWN")
        port_posture = f" | Portfolio: **{pl.replace('_', ' ')}**"

    health_icon = {"green": "🟢", "orange": "🟡", "red": "🔴"}.get(health_color, "⚪")

    return f"""\
## 1. Executive Summary

| Field | Value |
|-------|-------|
| Run date | {asof_date} |
| Macro posture | **{posture}** ({confidence} confidence) |
| Regime | {regime_label} |
| Health score | {health_icon} **{health_score}/100** ({health_color.upper()}){port_posture} |

"""


def _section_macro_regime(
    market_state: Dict,
    posture: str,
    rationale_section: str,
    regime_risks: str,
    triggers: str,
    alignment_section: str,
) -> str:
    risk_score = market_state.get("risk_score", 50)
    color = market_state.get("color", "orange").upper()
    bar = _bar(risk_score)

    regime_block = alignment_section if alignment_section else ""

    return f"""\
## 2. Current Macro Regime

**Risk Score**: {risk_score}/100 `{bar}` ({color})
{regime_block}
### Key Signals
{rationale_section}

### Regime Risk Probabilities
{regime_risks}

### What Would Change the Posture?
{triggers}

"""


def _section_portfolio_snapshot(interpretation: Optional[Dict], snapshot: Dict) -> str:
    if not interpretation:
        return """\
## 3. Portfolio Snapshot

> No portfolio interpretation available for this run.

"""

    n = interpretation.get("n_positions", 0)
    cash = interpretation.get("cash_pct", 0.0)
    currency = snapshot.get("currency", "USD")
    conc = interpretation.get("concentration", {})
    hhi = conc.get("hhi", 0.0)
    top4 = conc.get("top4_pct", 0.0)
    conc_warn = conc.get("warning", "OK")
    conc_icon = {"OK": "✅", "MODERATE": "⚠️", "HIGH": "🔴"}.get(conc_warn, "")

    # Top 5 table
    top5 = interpretation.get("top5_by_weight", [])
    if top5:
        rows = ["| Ticker | Weight | Sector | Asset Type | P&L | Fit |",
                "|--------|--------|--------|------------|-----|-----|"]
        for p in top5:
            pnl_str = f"{p['pnl_pct']:+.1f}%" if p.get("pnl_pct") is not None else "n/a"
            fit_icon = {"green": "✅", "orange": "🟡", "red": "🔴"}.get(p.get("macro_fit", ""), "⚪")
            rows.append(
                f"| {p['ticker']} | {p['weight_pct']:.1f}% | {p['sector']} | {p['asset_type']} | {pnl_str} | {fit_icon} |"
            )
        top5_table = "\n".join(rows)
    else:
        top5_table = "_No positions available._"

    # Factor breakdown inline
    factors = interpretation.get("by_factor", {})
    factor_lines = "  ".join(f"`{k}` {v:.0f}%" for k, v in factors.items() if v >= 1.0)

    # Sector breakdown (top 5)
    sectors = list(interpretation.get("by_sector", {}).items())[:5]
    sector_lines = " | ".join(f"{k} {v:.0f}%" for k, v in sectors)

    # Region breakdown
    regions = list(interpretation.get("by_region", {}).items())[:4]
    region_lines = " | ".join(f"{k} {v:.0f}%" for k, v in regions)

    # Asset type
    asset_types = list(interpretation.get("by_asset_type", {}).items())[:4]
    asset_type_lines = " | ".join(f"{k} {v:.0f}%" for k, v in asset_types)

    return f"""\
## 3. Portfolio Snapshot

**Positions**: {n} | **Cash**: {cash:.0f}% | **Currency**: {currency}
**Concentration**: {conc_icon} {conc_warn} — HHI {hhi:.3f} | Top-4 weight {top4:.0f}%

### Top 5 Holdings
{top5_table}

### Exposure Breakdown
- **By Factor**: {factor_lines if factor_lines else "n/a"}
- **By Sector**: {sector_lines if sector_lines else "n/a"}
- **By Region**: {region_lines if region_lines else "n/a"}
- **By Asset Type**: {asset_type_lines if asset_type_lines else "n/a"}

"""


def _section_alignment(
    interpretation: Optional[Dict],
    all_weather_alignment: Optional[Dict],
    market_state: Dict,
) -> str:
    if not interpretation and not all_weather_alignment:
        return ""

    lines = ["## 4. Regime Alignment Assessment\n"]

    regime_color = market_state.get("color", "orange")
    regime_word = {"green": "Risk-On", "orange": "Transitional", "red": "Risk-Off"}.get(
        regime_color, "Mixed"
    )

    if interpretation:
        posture_label = interpretation.get("posture_label", "UNKNOWN")
        narrative = interpretation.get("narrative_summary", "")
        posture_icon = {"ALIGNED": "✅", "PARTIALLY_ALIGNED": "⚠️", "MISALIGNED": "🔴"}.get(
            posture_label, "⚪"
        )
        lines.append(f"**Regime posture**: {regime_word} | **Portfolio alignment**: {posture_icon} {posture_label.replace('_', ' ')}\n")
        if narrative:
            lines.append(f"> {narrative}\n")

        # Protections
        protections = interpretation.get("regime_protections", [])
        if protections:
            lines.append("### ✅ Regime Protections")
            for p in protections:
                lines.append(f"- **{p['ticker']}** ({p['weight_pct']:.0f}%) — {p['reason']}")
            lines.append("")

        # Contradictions
        contradictions = interpretation.get("regime_contradictions", [])
        if contradictions:
            lines.append("### ⚠️ Regime Contradictions")
            for c in contradictions:
                lines.append(f"- **{c['ticker']}** ({c['weight_pct']:.0f}%) — {c['reason']}")
            lines.append("")

        # Missing sleeves
        missing = interpretation.get("missing_sleeves", [])
        if missing:
            lines.append("### 🔍 Missing Diversification Sleeves")
            for s in missing:
                lines.append(f"- **{s['sleeve']}**: {s['note']}")
            lines.append("")

    # All-Weather alignment overlay (if available from V1 engine)
    if all_weather_alignment:
        aw_posture = all_weather_alignment.get("posture", {})
        aw_gaps = all_weather_alignment.get("gaps_total_pct", [])
        lines.append("### All-Weather Allocation Gaps")
        if aw_gaps:
            gap_rows = ["| Asset Class | Gap | Action |",
                        "|-------------|-----|--------|"]
            for g in sorted(aw_gaps, key=lambda x: abs(x.get("gap", 0)), reverse=True)[:6]:
                action = g.get("action", "HOLD")
                icon = {"TRIM": "⬇️", "ADD": "⬆️", "HOLD": "➡️"}.get(action, "")
                gap_rows.append(
                    f"| {g['asset']} | {g['gap']:+.1f}% | {icon} {action} |"
                )
            lines.append("\n".join(gap_rows))
        lines.append("")

    return "\n".join(lines) + "\n"


def _section_risks(
    summary: Dict,
    alerts: Dict,
    interpretation: Optional[Dict],
) -> str:
    top_risks = summary.get("top_risks", [])
    top_opps = summary.get("top_opportunities", [])
    health_score = summary.get("health_score", 100)
    penalties = summary.get("breakdown", {}).get("penalties", {})

    alert_list = alerts.get("alerts", [])

    lines = ["## 5. Risks & Concentration Warnings\n"]

    # Redundant pairs
    if interpretation:
        pairs = interpretation.get("redundant_pairs", [])
        if pairs:
            lines.append("### Position Overlap / Redundancy")
            for pair in pairs:
                lines.append(
                    f"- {', '.join(pair['tickers'])} — {pair['note']}"
                )
            lines.append("")

    # Health score breakdown
    if penalties:
        lines.append("### Health Score Deductions")
        for k, v in penalties.items():
            lines.append(f"- `{k.replace('_', ' ')}`: {v:+d} pts")
        lines.append("")

    # Top risks from health score
    if top_risks:
        lines.append("### Top Portfolio Risks")
        for r in top_risks:
            lines.append(f"- ⚠️ {r}")
        lines.append("")

    # Triggered alerts
    if alert_list:
        lines.append("### Active Alerts")
        for a in alert_list:
            sev = a.get("severity", "info").upper()
            lines.append(f"- [{sev}] {a.get('rule_name', '?')}: {a.get('message', '')}")
        lines.append("")

    # Opportunities
    if top_opps:
        lines.append("### Opportunities Identified")
        for o in top_opps:
            lines.append(f"- 💡 {o}")
        lines.append("")

    if not (top_risks or alert_list or (interpretation and interpretation.get("redundant_pairs"))):
        lines.append("_No significant risk flags at this time._\n")

    return "\n".join(lines) + "\n"


def _section_watchpoints(
    action_bullets: str,
    all_weather_alignment: Optional[Dict],
    interpretation: Optional[Dict],
) -> str:
    lines = ["## 6. Watchpoints & Rebalance Considerations\n"]

    lines.append(
        "> _The following are analytical observations and scenario-based considerations, "
        "not personalized investment advice. Rebalancing decisions should account for "
        "transaction costs, tax implications, and individual risk tolerance._\n"
    )

    # All-weather recommended actions
    if all_weather_alignment:
        recs = all_weather_alignment.get("recommended_actions", {})
        top3 = recs.get("top_3_actions", [])
        if top3 and top3[0].get("action") != "HOLD":
            lines.append("### All-Weather Rebalancing Signals")
            for a in top3:
                action = a.get("action", "HOLD")
                if action != "HOLD":
                    lines.append(f"- **{action}** {a['asset']} — {a.get('why', '')}")
            notes = recs.get("notes", [])
            for n in notes:
                lines.append(f"- ⚠️ {n}")
            lines.append("")

    # Missing sleeves as action prompts
    if interpretation:
        missing = interpretation.get("missing_sleeves", [])
        if missing:
            lines.append("### Diversification Gaps to Monitor")
            for s in missing:
                lines.append(f"- Consider **{s['sleeve']}** exposure: {s['note']}")
            lines.append("")

    # Decision engine / posture-driven bullets
    if action_bullets:
        lines.append("### Posture-Driven Action Set")
        lines.append(action_bullets)
        lines.append("")

    return "\n".join(lines) + "\n"


def _section_appendix(
    ts_str: str,
    summary: Dict,
    market_state: Dict,
    interpretation: Optional[Dict],
) -> str:
    compact = {
        "run": ts_str,
        "health_score": summary.get("health_score"),
        "health_color": summary.get("health_color"),
        "risk_score": market_state.get("risk_score"),
        "market_color": market_state.get("color"),
        "regime_probs": market_state.get("regime_probabilities", {}),
    }
    if interpretation:
        compact["portfolio"] = {
            "n_positions": interpretation.get("n_positions"),
            "cash_pct": interpretation.get("cash_pct"),
            "posture_label": interpretation.get("posture_label"),
            "concentration_warning": interpretation.get("concentration", {}).get("warning"),
            "hhi": interpretation.get("concentration", {}).get("hhi"),
            "missing_sleeves": [s["sleeve"] for s in interpretation.get("missing_sleeves", [])],
        }

    return f"""\
## 7. Machine-Readable Appendix

```json
{json.dumps(compact, indent=2)}
```
"""


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def generate_markdown_report(
    ts_str: str,
    summary: Dict[str, Any],
    alerts: Dict[str, Any],
    market_state: Dict[str, Any],
    portfolio_state: Dict[str, Any],
    all_weather_alignment: Optional[Dict[str, Any]] = None,
    portfolio_interpretation: Optional[Dict[str, Any]] = None,
    snapshot: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Generates the 7-section Portfolio Intelligence Brief for Zapier email delivery.

    Parameters
    ----------
    ts_str : run timestamp string (YYYYMMDDTHHMMSS)
    summary : health score dict
    alerts : triggered alerts dict
    market_state : macro regime / indicator dict
    portfolio_state : enriched portfolio with positions, exposures, concentration
    all_weather_alignment : optional all-weather alignment artifact (may be None)
    portfolio_interpretation : optional output of portfolio_interpreter.interpret_portfolio()
    snapshot : normalized eToro snapshot (used for currency / cash_pct fallback)
    """
    report_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "out", f"report_{ts_str}.md"
    )
    snapshot = snapshot or {}

    # ---- Pull common values ------------------------------------------------
    asof_date = market_state.get("timestamp", ts_str)[:10]
    health_score = summary.get("health_score", 100)
    health_color = summary.get("health_color", "green")

    inds = market_state.get("indicators", {})
    sub_scores = market_state.get("sub_scores", {})
    r_probs = market_state.get("regime_probabilities", {})

    # ---- Derive posture & confidence ---------------------------------------
    risk_overlay = portfolio_state.get("risk_overlay", {})
    macro = risk_overlay.get("macro_regime", {})
    p_b = float(macro.get("p_bull", 0.5))
    p_dd20 = float(macro.get("p_drawdown_20", 0.0))
    p_dd10 = float(macro.get("p_drawdown_10", 0.0))
    reg_state = str(macro.get("regime_state", "UNKNOWN"))

    v5_present = "p_drawdown_20" in macro or "p_bull" in macro
    is_degenerate = (
        reg_state == "UNKNOWN"
        or abs(p_b - 0.5) < 0.02
        or (p_dd20 < 0.005 and p_dd10 < 0.005)
    )
    v5_usable = v5_present and not is_degenerate

    ms_score = market_state.get("risk_score", 50)
    cpi = inds.get("inflation", {}).get("cpi_headline_yoy")
    pmi = inds.get("growth", {}).get("pmi_level")
    key_data_missing = cpi is None or pmi is None

    posture, confidence, rationale_why, action_bullets = _derive_posture(
        all_weather_alignment, v5_usable, macro, ms_score, key_data_missing,
        sub_scores, r_probs
    )

    # Regime label for summary
    aw_regime = None
    if all_weather_alignment:
        aw_regime = all_weather_alignment.get("macro_regime", {})
    regime_label = _build_regime_label(aw_regime, market_state)

    # ---- Apply sub-score hard caps (when no AW alignment) ------------------
    if not all_weather_alignment:
        usd_color = sub_scores.get("usd_stress", {}).get("color", "green").lower()
        com_color = sub_scores.get("commodities_stress", {}).get("color", "green").lower()
        if (usd_color == "red" or com_color == "red") and ms_score < 70 and posture == "RISK-ON":
            posture = "NEUTRAL"
            rationale_why += " (Hard cap: severe USD or commodity stress.)"
        if key_data_missing and confidence == "High":
            confidence = "Medium"

    # ---- Rationale signals section ----------------------------------------
    rationale_section = _build_rationale_section(inds, cpi)

    # ---- Regime risk probabilities section ---------------------------------
    regime_risks = (
        f"- **Recession**: {_band(r_probs.get('recession_risk'))}\n"
        f"- **Liquidity Stress**: {_band(r_probs.get('liquidity_stress_risk'))}\n"
        f"- **Inflation Resurgence**: {_band(r_probs.get('inflation_resurgence_risk'))}\n"
        f"- **Policy Shock**: {_band(r_probs.get('policy_shock_risk'))}"
    )

    # ---- Flip triggers -------------------------------------------------------
    triggers = _build_triggers(posture)

    # ---- All-Weather alignment section (brief bullets) ----------------------
    alignment_section = ""
    if all_weather_alignment:
        briefs = all_weather_alignment.get("brief_bullets", [])
        other_briefs = briefs[1:] if len(briefs) > 1 else []
        if other_briefs:
            alignment_section = "\n".join(f"- {b}" for b in other_briefs) + "\n"

    # ---- Assemble action bullets if not already set by AW alignment --------
    if not action_bullets:
        action_bullets = _default_action_bullets(posture)

    # ---- Dry powder --------------------------------------------------------
    port_sum = portfolio_state.get("portfolio_summary", {})
    cash_val = port_sum.get("cash_pct", snapshot.get("cash_pct", 0.0))
    dry_powder = "High" if cash_val > 0.25 else ("Medium" if cash_val > 0.10 else "Low")

    # ---- Build all sections ------------------------------------------------
    s1 = _section_executive_summary(
        ts_str, asof_date, posture, confidence, health_score, health_color,
        regime_label, portfolio_interpretation
    )
    s2 = _section_macro_regime(
        market_state, posture, rationale_section, regime_risks,
        triggers, alignment_section
    )
    s3 = _section_portfolio_snapshot(portfolio_interpretation, snapshot)
    s4 = _section_alignment(portfolio_interpretation, all_weather_alignment, market_state)
    s5 = _section_risks(summary, alerts, portfolio_interpretation)
    s6 = _section_watchpoints(action_bullets, all_weather_alignment, portfolio_interpretation)
    s7 = _section_appendix(ts_str, summary, market_state, portfolio_interpretation)

    # ---- Compose final document --------------------------------------------
    header = (
        f"# Portfolio Intelligence Brief — {ts_str}\n"
        f"_Generated automatically | Data as-of {asof_date} | "
        f"Posture: **{posture}** ({confidence}) | Dry powder: {dry_powder} ({cash_val * 100:.0f}%)_\n\n"
        f"---\n\n"
    )

    md_content = header + s1 + s2 + s3 + s4 + s5 + s6 + s7 + (
        "\n---\n_Analytical observations only. Not financial advice. "
        "Review before acting on any rebalancing considerations._\n"
    )

    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    with open(report_path, "w") as f:
        f.write(md_content)

    return report_path


# ---------------------------------------------------------------------------
# Private helpers (posture derivation — preserves existing V5 logic)
# ---------------------------------------------------------------------------

def _derive_posture(
    all_weather_alignment, v5_usable, macro, ms_score, key_data_missing,
    sub_scores, r_probs
):
    """Derive posture, confidence, rationale_why, action_bullets in priority order."""
    posture = "NEUTRAL"
    confidence = "Medium"
    rationale_why = "Balancing mixed signals in the macro regime."
    action_bullets = ""

    if all_weather_alignment:
        post = all_weather_alignment.get("posture", {})
        posture = post.get("posture", "NEUTRAL")
        confidence = post.get("confidence_label", "MEDIUM").capitalize()
        briefs = all_weather_alignment.get("brief_bullets", [])
        if briefs:
            rationale_why = briefs[0].strip("- ")
        recs = all_weather_alignment.get("recommended_actions", {})
        action_list = []
        for a in recs.get("top_3_actions", []):
            if a["action"] != "HOLD":
                action_list.append(f"- {a['action']} {a['asset']} ({a['why']})")
        if not action_list:
            action_list.append("- HOLD current core allocations.")
        for n in recs.get("notes", []):
            action_list.append(f"- Note: {n}")
        action_bullets = "\n".join(action_list)

    elif v5_usable:
        tl = str(macro.get("traffic_light", "ORANGE")).upper()
        p_comp = float(macro.get("p_drawdown_composite", 0.1))
        if tl == "GREEN":
            posture = "RISK-ON"
            confidence = "High" if p_comp < 0.05 else ("Medium" if p_comp < 0.15 else "Low")
            rationale_why = "V5 Econometrics signal strong expansionary resilience and low drawdown probability."
        elif tl == "RED":
            posture = "RISK-OFF"
            confidence = "High" if p_comp > 0.30 else ("Medium" if p_comp > 0.20 else "Low")
            rationale_why = "V5 Econometrics identify statistically elevated drawdown risk and weak fundamentals."
        else:
            posture = "NEUTRAL"
            confidence = "Medium"
            rationale_why = "V5 Econometrics indicate transition or conflicting constraints."

    else:
        if ms_score <= 35:
            posture = "RISK-OFF"
            rationale_why = "Heuristic metrics heavily oversold/stressed; V5 degraded so leaning defensive."
            confidence = "Medium" if not key_data_missing else "Low"
        elif ms_score >= 70:
            posture = "RISK-ON"
            rationale_why = "Broad heuristic indicators show strength, though missing V5 complex validation."
            confidence = "Medium" if not key_data_missing else "Low"
        else:
            posture = "NEUTRAL"
            rationale_why = "Heuristic indicators scattered around historical averages."
            confidence = "Medium" if not key_data_missing else "Low"

    return posture, confidence, rationale_why, action_bullets


def _build_regime_label(aw_regime: Optional[Dict], market_state: Dict) -> str:
    if aw_regime:
        base = aw_regime.get("regime_base", "Unknown")
        overlay = aw_regime.get("regime_overlay", "None")
        conf = aw_regime.get("confidence", "?")
        label = base
        if overlay and overlay != "None":
            label += f" + {overlay}"
        return f"{label} (confidence {conf})"
    color = market_state.get("color", "orange")
    score = market_state.get("risk_score", 50)
    return f"Heuristic {color.capitalize()} ({score}/100)"


def _build_rationale_section(inds: Dict, cpi) -> str:
    vol = inds.get("volatility", {})
    trend = inds.get("trend", {})
    credit = inds.get("credit", {})
    rates = inds.get("rates", {})
    usd_gold = inds.get("usd_gold", {})

    vix = vol.get("vix_level")
    if vix is None:
        vix_line = "- **VIX**: data missing"
    else:
        vix_eval = "Calm" if vix < 20 else ("Elevated" if vix < 25 else "High stress")
        vix_line = f"- **VIX**: {_num(vix)} → {vix_eval} (calm <20, stress >25)"

    ndx_p = trend.get("ndx", {}).get("price")
    ndx_ma200 = trend.get("ndx", {}).get("ma200")
    if ndx_p is not None and ndx_ma200 is not None:
        ndx_eval = "Bullish" if ndx_p > ndx_ma200 else "Bearish"
        ndx_line = f"- **NDX trend**: {int(ndx_p)} vs MA200 {int(ndx_ma200)} → {ndx_eval} primary trend"
    else:
        ndx_line = "- **NDX trend**: data missing"

    hy = credit.get("hy_spread_level")
    if hy is None:
        hy_line = "- **HY Spread**: data missing"
    else:
        hy_eval = "Benign" if hy < 4.0 else ("Watch" if hy < 6.0 else "Stress")
        hy_line = f"- **HY Credit Spread**: {_num(hy)} → {hy_eval} (stress >6)"

    yc = rates.get("yield_curve_10y_2y")
    if yc is None:
        yc_line = "- **Yield Curve**: data missing"
    else:
        yc_eval = "Inverted (recessionary)" if yc < 0 else "Normal"
        yc_line = f"- **Yield Curve (10Y-2Y)**: {_num(yc)} → {yc_eval}"

    dxy = usd_gold.get("dxy_above_ma50")
    dxy_line = f"- **USD (DXY)**: {'Above MA50 → tightening' if dxy else 'Below MA50 → benign'}" if dxy is not None else "- **USD**: data missing"

    inf_line = (
        f"- **CPI YoY**: {_num(cpi, 1)}% → {'Elevated' if cpi and cpi > 3.0 else 'Under control'}"
        if cpi is not None else "- **CPI YoY**: data missing"
    )

    return "\n".join([vix_line, ndx_line, hy_line, yc_line, dxy_line, inf_line])


def _build_triggers(posture: str) -> str:
    if posture == "RISK-ON":
        return (
            "- NDX falls decisively below MA200.\n"
            "- VIX closes above 25 for 3 consecutive sessions.\n"
            "- HY spread rises above 4.5 and trend is steepening."
        )
    if posture == "NEUTRAL":
        return (
            "- **(→ RISK-ON)**: NDX breaks above MA50 with yield curve steepening.\n"
            "- **(→ RISK-OFF)**: VIX > 25 while liquidity stress probability > 35%.\n"
            "- **(→ RISK-OFF)**: CPI YoY accelerates above 3.5% causing policy shock risk to spike."
        )
    return (
        "- **(→ NEUTRAL)**: VIX retreats below 20 for one full week.\n"
        "- **(→ NEUTRAL)**: HY spreads tighten back below 5.0.\n"
        "- **(→ RISK-ON)**: NDX recovers and holds above MA200."
    )


def _default_action_bullets(posture: str) -> str:
    if posture == "RISK-ON":
        return "- Increase beta gradually\n- Prefer quality growth exposure\n- Review hedge positions for drag"
    if posture == "NEUTRAL":
        return "- Maintain core allocations\n- Add selectively on confirmed dips\n- Keep dry powder ready"
    return "- Reduce beta / cyclical exposure\n- Raise cash or defensives weight\n- Consider tail-risk hedges"
