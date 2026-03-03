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

def generate_markdown_report(ts_str: str, summary: Dict[str, Any], alerts: Dict[str, Any]) -> str:
    """Generates a lightweight markdown report of the latest run."""
    report_path = os.path.join(os.path.dirname(__file__), "..", "..", "out", f"report_{ts_str}.md")
    
    score = summary.get('health_score', 'N/A')
    color = summary.get('health_color', 'unknown')
    
    risks = "\n".join([f"- {r}" for r in summary.get('top_risks', [])]) or "- None flagged."
    opps = "\n".join([f"- {o}" for o in summary.get('top_opportunities', [])]) or "- None flagged."
    
    alert_lines = ""
    for a in alerts.get("alerts", []):
        alert_lines += f"- **[{a['severity'].upper()}]** {a['rule_name']}: {a['message']} (Trigger: {a['trigger_value']})\n"
        
    if not alert_lines:
        alert_lines = "- No alerts triggered this run."
        
    md_content = f"""# Portfolio Run Report ({ts_str})

## Summary
- **Health Score**: {score}/100 
- **Regime Color Category**: {color.upper()}

## Top Risks
{risks}

## Top Opportunities
{opps}

## Active Alerts
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
