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
    
    score = summary.get('health_score', 'N/A')
    color = summary.get('health_color', 'unknown')
    
    # Logistic interpretation
    if isinstance(score, (int, float)):
        if score >= 75:
            logistic_label = "🟢 RISK ON"
        elif score >= 50:
            logistic_label = "🟠 NEUTRAL"
            color = "orange"
        else:
            logistic_label = "🔴 RISK OFF"
    else:
        logistic_label = "⚪ UNKNOWN"

    # Market Drivers
    inds = market_state.get('indicators', {})
    recession_risk = inds.get('recession_risk', 0.0)
    liquidity_risk = inds.get('liquidity_stress_risk', 0.0)
    inflation_risk = inds.get('inflation_resurgence_risk', 0.0)
    
    market_drivers = f"""- **Recession Risk**: {recession_risk*100:.1f}% `[Range: 0-100%]`
- **Liquidity Stress**: {liquidity_risk*100:.1f}% `[Range: 0-100%]`
- **Inflation Risk**: {inflation_risk*100:.1f}% `[Range: 0-100%]`"""

    # Portfolio Diagnostics
    port_sum = portfolio_state.get('portfolio_summary', {})
    hhi = port_sum.get('hhi', 0.0)
    cash_pwd = portfolio_state.get('cash_pct', 0.0)
    
    port_diagnostics = f"""- **Cash Position**: {cash_pwd*100:.1f}% `[Range: 0-100%]`
- **Concentration (HHI)**: {hhi:.3f} `[Ideal < 0.15, High > 0.25]`"""

    risks = "\n".join([f"- {r}" for r in summary.get('top_risks', [])]) or "- None flagged."
    opps = "\n".join([f"- {o}" for o in summary.get('top_opportunities', [])]) or "- None flagged."
    
    alert_lines = ""
    for a in alerts.get("alerts", []):
        alert_lines += f"- **[{a['severity'].upper()}]** {a['rule_name']}: {a['message']} (Trigger: {a['trigger_value']})\n"
        
    if not alert_lines:
        alert_lines = "- No alerts triggered this run."
        
    md_content = f"""# Portfolio Run Report ({ts_str})

## 🧭 Regime Positioning (Logistic Approach)
- **Posture**: {logistic_label}
- **Algorithmic Health Score**: {score}/100 
- **Regime Color**: {color.upper()}

### 📊 Market Drivers
{market_drivers}

### 💼 Portfolio Diagnostics
{port_diagnostics}

## ⚠️ Top Risks
{risks}

## 💡 Top Opportunities
{opps}

## 🚨 Active Alerts
{alert_lines}

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
