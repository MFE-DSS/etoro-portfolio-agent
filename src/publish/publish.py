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
    """Generates a lightweight markdown report of the latest run."""
    report_path = os.path.join(os.path.dirname(__file__), "..", "..", "out", f"report_{ts_str}.md")
    
    # helper for %
    def fmt_pct(val):
        if val is None: return "N/A"
        return f"{float(val)*100:.1f}%"

    # --- wiring status ---
    risk_overlay = portfolio_state.get('risk_overlay', {})
    macro = risk_overlay.get('macro_regime', {})
    
    # Check if V5 is present (has fields like p_drawdown_composite)
    v5_present = "p_drawdown_20" in macro or "p_bull" in macro
    
    # Degeneracy check
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
        # We assume drawdown ~0.0 means degenerate
        is_degenerate = True

    v5_status_str = "DEGRADED (probabilities degenerate)" if is_degenerate else "OK"
    if not v5_present: v5_status_str = "MISSING"

    # missing metadata count
    missing_meta_count = sum(1 for p in portfolio_state.get('positions', []) if p.get('asset_type') == 'UNKNOWN' or p.get('sector') == 'UNKNOWN')
    if missing_meta_count == 0 and "MISSING_ASSET_METADATA" in risk_overlay.get("flags", []):
        missing_meta_count = 1 # fallback if positions list is missing but flag is present

    wiring_status = f"""**Wiring Status:**
- Macro V5 Present: {'Yes' if v5_present else 'No'}
- Macro V5 Usable: {'No' if is_degenerate else 'Yes'}
- Missing Metadata Count: {missing_meta_count}
"""

    # --- A) Portfolio Health ---
    h_score = summary.get('health_score', 'N/A')
    h_color = summary.get('health_color', 'UNKNOWN').upper()
    penalties = summary.get('penalties', {})
    pen_str = ""
    for k, v in penalties.items():
        pen_str += f"  - {k}: -{v}\n"
    if not pen_str: pen_str = "  - None\n"
    
    risks = "\n".join([f"- {r}" for r in summary.get('top_risks', [])]) or "- None flagged."
    
    sec_a = f"""## A) Portfolio Health (Pipeline Quality)
- **Health Score**: {h_score}/100 ({h_color})
- **Penalties**:
{pen_str}
- **Top Risks**:
{risks}
"""

    # --- B) Macro Regime (V5 Models) ---
    if is_degenerate:
        v5_headline = "⚪ V5 status: DEGRADED (probabilities degenerate)"
    else:
        tl = str(macro.get('traffic_light', 'UNKNOWN')).upper()
        if tl == "GREEN": tl_icon = "🟢"
        elif tl == "ORANGE": tl_icon = "🟠"
        elif tl == "RED": tl_icon = "🔴"
        else: tl_icon = "⚪"
        v5_headline = f"{tl_icon} {tl} (Score: {macro.get('macro_score', 50.0):.1f}/100, State: {reg_state})"

    sec_b = f"""## B) Macro Regime (V5 Models)
{v5_headline}
- **Regime State**: {reg_state}
- **P(Bull)**: {fmt_pct(macro.get('p_bull'))}
- **P(Drawdown 10%)**: {fmt_pct(macro.get('p_drawdown_10'))}
- **P(Drawdown 20%)**: {fmt_pct(macro.get('p_drawdown_20'))}
- **P(Drawdown Composite)**: {fmt_pct(macro.get('p_drawdown_composite'))}
- **Buy The Dip Ok?**: {macro.get('buy_the_dip_ok', False)}
- **Recommended Action**: {macro.get('recommended_action', 'HOLD')}
"""

    # --- C) Market State (Heuristic) ---
    ms_score = market_state.get('risk_score', 'N/A')
    ms_color = str(market_state.get('color', 'UNKNOWN')).upper()
    if ms_color == "GREEN": ms_icon = "🟢"
    elif ms_color == "ORANGE": ms_icon = "🟠"
    elif ms_color == "RED": ms_icon = "🔴"
    else: ms_icon = "⚪"
    
    sub_scores = market_state.get('sub_scores', {})
    ss_str = ""
    for k, v in sub_scores.items():
        ss_str += f"  - {k}: {v.get('score','N/A')}/100 ({str(v.get('color','')).upper()})\n"
        
    inds = market_state.get('indicators', {})
    ind_str = ""
    for k, v in inds.items():
        if isinstance(v, float) and 0.0 <= v <= 1.0 and ("risk" in k or "prob" in k):
            ind_str += f"  - {k}: {fmt_pct(v)}\n"
        else:
            ind_str += f"  - {k}: {v}\n"
            
    r_probs = market_state.get('regime_probabilities', {})
    rp_str = ""
    for k, v in r_probs.items():
        rp_str += f"  - {k}: {fmt_pct(v)}\n"

    sec_c = f"""## C) Market State (Heuristic Explainability)
- **Heuristic Score**: {ms_score}/100 {ms_icon}
- **Sub Scores**:
{ss_str}
- **Indicators**:
{ind_str}
- **Regime Probabilities**:
{rp_str}
"""

    # --- Assemble ---
    port_sum = portfolio_state.get('portfolio_summary', {})
    cash_val = port_sum.get('cash_pct', portfolio_state.get('cash_pct', 0.0))
    
    headline_state = reg_state if not is_degenerate else "UNKNOWN"

    md_content = f"""# Portfolio Run Report ({ts_str})
{wiring_status}
## 🧭 Regime Positioning
- **Target Posture**: {headline_state}
- **Cash Position**: {fmt_pct(cash_val)}

{sec_a}
{sec_b}
{sec_c}
*Note: This report is a lightweight human-readable version of the deterministic pipeline artifacts.*
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
