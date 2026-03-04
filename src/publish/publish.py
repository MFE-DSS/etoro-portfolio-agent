import os
import shutil
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

def zip_run_bundle(bundle_dir: str) -> str:
    """Zips the nested bundle directory for easy transport."""
    output_filename = bundle_dir  # shutil.make_archive adds the .zip extension
    archive_path = shutil.make_archive(output_filename, 'zip', bundle_dir)
    return archive_path

def generate_markdown_report(ts_str: str, summary: Dict[str, Any], alerts: Dict[str, Any], market_state: Dict[str, Any], portfolio_state: Dict[str, Any]) -> str:
    """Generates the Macro Posture Brief (BETA) report."""
    report_path = os.path.join(os.path.dirname(__file__), "..", "..", "out", f"report_{ts_str}.md")
    
    def fmt_pct(val):
        if val is None: return "missing"
        return f"{float(val)*100:.0f}%"

    def fmt_num(val, dec=2):
        if val is None: return "missing"
        return f"{float(val):.{dec}f}"

    def fmt_price(val):
        if val is None: return "missing"
        return f"{int(val)}"

    # --- wiring status ---
    risk_overlay = portfolio_state.get('risk_overlay', {})
    macro = risk_overlay.get('macro_regime', {})
    
    v5_present = "p_drawdown_20" in macro or "p_bull" in macro
    p_b = float(macro.get("p_bull", 0.5))
    p_dd20 = float(macro.get("p_drawdown_20", 0.0))
    p_dd10 = float(macro.get("p_drawdown_10", 0.0))
    reg_state = str(macro.get("regime_state", "UNKNOWN"))
    
    is_degenerate = False
    if reg_state == "UNKNOWN":
        is_degenerate = True
    elif abs(p_b - 0.5) < 0.02:
        is_degenerate = True
    elif (p_dd20 < 0.005 and p_dd10 < 0.005):
        is_degenerate = True

    v5_usable = v5_present and not is_degenerate
    missing_meta_count = sum(1 for p in portfolio_state.get('positions', []) if p.get('asset_type') == 'UNKNOWN' or p.get('sector') == 'UNKNOWN')
    if missing_meta_count == 0 and "MISSING_ASSET_METADATA" in risk_overlay.get("flags", []):
        missing_meta_count = 1 

    # --- PULL MARKET STATE ---
    ms_score = market_state.get('risk_score', 50)
    inds = market_state.get('indicators', {})
    sub_scores = market_state.get('sub_scores', {})
    r_probs = market_state.get('regime_probabilities', {})
    asof_date = market_state.get("timestamp", ts_str)[:10]

    # --- IS MISSING DATA? ---
    inf = inds.get("inflation", {})
    gro = inds.get("growth", {})
    cpi = inf.get("cpi_headline_yoy")
    pmi = gro.get("pmi_level")
    key_data_missing = (cpi is None or pmi is None)

    # --- POSTURE DECISION LOGIC (BETA) ---
    posture = "NEUTRAL"
    confidence = "Medium"
    rationale_why = "Balancing mixed signals in the macro regime."

    if v5_usable:
        tl = str(macro.get('traffic_light', 'ORANGE')).upper()
        p_comp = float(macro.get('p_drawdown_composite', 0.1))
        
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
            rationale_why = "V5 Econometrics indicate transition or conflicting constraints (neither extreme)."
    else:
        # Fallback to heuristic
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
            
    # Sub-score RED cap constraint
    usd_color = sub_scores.get('usd_stress', {}).get('color', 'green').lower()
    com_color = sub_scores.get('commodities_stress', {}).get('color', 'green').lower()
    hard_red = (usd_color == 'red' or com_color == 'red')
    
    if hard_red and ms_score < 70 and posture == "RISK-ON":
        posture = "NEUTRAL"
        rationale_why += " (Capped at NEUTRAL: Severe USD or Commodities stress triggered hard bounds)."
        
    if key_data_missing and confidence == "High":
        confidence = "Medium"

    # Action Sets
    action_bullets = ""
    if posture == "RISK-ON":
        action_bullets = "- Increase beta gradually\n- Prefer quality growth\n- Avoid hedges"
    elif posture == "NEUTRAL":
        action_bullets = "- Maintain core\n- Add selectively on dips\n- Keep dry powder"
    else:
        action_bullets = "- Reduce beta\n- Raise cash / defensives\n- Hedge tail risk"

    # --- RATIONALE (5-7 SIGNALS) ---
    vix = inds.get("volatility", {}).get("vix_level")
    vix_str = f"{fmt_num(vix)} vs <20 calm, >25 stress"
    if vix is None: vix_eval = "missing"
    elif vix < 20: vix_eval = "Calm background"
    elif vix < 25: vix_eval = "Elevated but not panic"
    else: vix_eval = "High stress regime"
    
    ndx_p = inds.get("trend", {}).get("ndx", {}).get("price")
    ndx_ma200 = inds.get("trend", {}).get("ndx", {}).get("ma200")
    if ndx_p is not None and ndx_ma200 is not None:
        ndx_eval = "Bullish primary trend" if ndx_p > ndx_ma200 else "Bearish primary trend"
        ndx_str = f"NDX {fmt_price(ndx_p)} vs MA200 {fmt_price(ndx_ma200)} \u2192 {ndx_eval}"
    else:
        ndx_str = "NDX Trend: Data missing (not used)"

    hy = inds.get("credit", {}).get("hy_spread_level")
    if hy is None: hy_str = "HY Spread: Data missing"
    else:
        hy_eval = "Benign credit conditions" if hy < 4.0 else ("Watch levels" if hy < 6.0 else "Credit stress")
        hy_str = f"HY Spread {fmt_num(hy)} vs >6 stress \u2192 {hy_eval}"
        
    yc = inds.get("rates", {}).get("yield_curve_10y_2y")
    if yc is None: yc_str = "Yield Curve: Data missing"
    else:
        yc_eval = "Recessionary inversion" if yc < 0 else "Normal upward sloped"
        yc_str = f"Yield Curve (10y-2y) {fmt_num(yc)} \u2192 {yc_eval}"

    dxy_ma = inds.get("usd_gold", {}).get("dxy_above_ma50")
    if dxy_ma is None:
        dxy_str = "USD Trend: Data missing"
    else:
        dxy_eval = "Yes \u2192 Dollar tightening" if dxy_ma else "No \u2192 Dollar benign"
        dxy_str = f"USD (DXY) above MA50: {dxy_eval}"
    
    if cpi is None:
        inf_str = "- Inflation CPI: Data missing (not used)"
    else:
        inf_str = f"- CPI YoY: {fmt_num(cpi, 1)}% \u2192 {'Elevated' if cpi>3.0 else 'Under control'}"
        
    rationale_section = f"""- **VIX**: {vix_str} \u2192 {vix_eval}
- **Trend**: {ndx_str}
- **Credit**: {hy_str}
- **Rates**: {yc_str}
- **USD Stress**: {dxy_str}
{inf_str}"""

    # --- REGIME RISKS ---
    def band_prob(v):
        if v is None: return "Missing"
        if v <= 0.15: return f"{fmt_pct(v)} (Low)"
        if v <= 0.35: return f"{fmt_pct(v)} (Moderate)"
        return f"{fmt_pct(v)} (High)"
        
    r_reces = r_probs.get("recession_risk", 0.0)
    r_liq = r_probs.get("liquidity_stress_risk", 0.0)
    r_inf = r_probs.get("inflation_resurgence_risk", 0.0)
    r_pol = r_probs.get("policy_shock_risk", 0.0)

    regime_risks = f"""- **Liquidity Stress**: {band_prob(r_liq)}
  *Risk of broad forced selling and correlation spikes.*
- **Recession Risk**: {band_prob(r_reces)}
  *Risk of earnings compression and prolonged down-cycle.*
- **Inflation Resurgence**: {band_prob(r_inf)}
  *Risk of higher-for-longer rates impairing multiples.*
- **Policy Shock**: {band_prob(r_pol)}
  *Risk of unexpected hawkish pivot.*"""

    # --- FLIP TRIGGERS ---
    if posture == "RISK-ON":
        triggers = "- NDX falls decisively below MA200.\n- VIX closes > 25 for 3 consecutive sessions.\n- HY spread rises > 4.5 and trend is steepening."
    elif posture == "NEUTRAL":
        triggers = "- (To RISK-ON): NDX breaks above MA50 with Yield Curve steepening > 0.\n- (To RISK-OFF): VIX > 25 while Liquidity Stress probability breaks > 35%.\n- (To RISK-OFF): CPI YoY accelerates > 3.5% causing Policy Shock to spike."
    else:
        triggers = "- (To NEUTRAL): VIX retreats below 20 for one full week.\n- (To NEUTRAL): Credit spreads (HY) tighten back below 5.0.\n- (To RISK-ON): NDX recovers and holds above MA200."

    # Cash / Budget
    port_sum = portfolio_state.get('portfolio_summary', {})
    cash_val = port_sum.get('cash_pct', portfolio_state.get('cash_pct', 0.0))
    dry_powder = "High" if cash_val > 0.25 else ("Medium" if cash_val > 0.10 else "Low")

    # --- ASSEMBLE MD ---
    md_content = f"""# Macro Posture Brief (BETA) — {ts_str}
*Data Freshness (As-of Date): {asof_date}*
*Wiring Status: V5 Present={'Yes' if v5_present else 'No'}, Usable={'Yes' if v5_usable else 'No'}, Missing Meta={missing_meta_count}*

## 1. Decision Focus
- **Posture**: **{posture}**
- **Confidence**: {confidence}
- **Why now**: {rationale_why}
- **Risk Budget**: Dry powder is {dry_powder} ({fmt_pct(cash_val)})

**Recommended Action Set:**
{action_bullets}

## 2. Rationale (Market Pricing)
{rationale_section}

## 3. Regime Risks
{regime_risks}

## 4. What would change my mind?
{triggers}

---
*This report is macro-only BETA; portfolio diagnostics removed by design.*
"""
    
    with open(report_path, "w") as f:
        f.write(md_content)
        
    return report_path
    
def optional_google_drive_upload(zip_path: str):
    """Stubbed Drive uploader behind a strict opt-in env flag."""
    if os.environ.get("ENABLE_GDRIVE_UPLOAD") == "true":
        logger.info(f"ENABLE_GDRIVE_UPLOAD=true. [Dry Run] Would upload {zip_path} to Google Drive.")
    else:
        logger.debug("Google Drive upload disabled.")
