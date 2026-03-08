import os
import yaml
import markdown
import requests
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Inline CSS for email-client-safe HTML rendering
# ---------------------------------------------------------------------------
_EMAIL_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
       font-size: 14px; line-height: 1.6; color: #1a1a1a; background: #f5f5f5; margin: 0; padding: 0; }
.wrapper { max-width: 760px; margin: 24px auto; background: #ffffff;
           border-radius: 6px; border: 1px solid #e0e0e0; overflow: hidden; }
.header { background: #1a1a2e; color: #ffffff; padding: 20px 28px; }
.header h1 { margin: 0; font-size: 18px; font-weight: 600; }
.header p { margin: 4px 0 0; font-size: 12px; color: #aaaacc; }
.body { padding: 24px 28px; }
h2 { font-size: 15px; font-weight: 700; color: #1a1a2e;
     border-bottom: 2px solid #e8e8e8; padding-bottom: 6px; margin-top: 28px; margin-bottom: 12px; }
h3 { font-size: 13px; font-weight: 600; color: #333; margin-top: 16px; margin-bottom: 8px; }
p, li { font-size: 13px; }
table { border-collapse: collapse; width: 100%; margin: 10px 0; font-size: 12px; }
th { background: #f0f0f5; color: #333; text-align: left; padding: 7px 10px;
     border: 1px solid #d8d8e0; font-weight: 600; }
td { padding: 6px 10px; border: 1px solid #e4e4e8; vertical-align: top; }
tr:nth-child(even) td { background: #fafafa; }
code { background: #f4f4f8; padding: 2px 5px; border-radius: 3px;
       font-family: 'SF Mono', Consolas, monospace; font-size: 11px; color: #333; }
pre { background: #f4f4f8; padding: 12px; border-radius: 4px; overflow-x: auto;
      font-size: 11px; border: 1px solid #e0e0e8; }
blockquote { border-left: 3px solid #aaaacc; margin: 8px 0; padding: 6px 12px;
             color: #555; background: #f9f9fc; font-style: italic; }
hr { border: none; border-top: 1px solid #e8e8e8; margin: 20px 0; }
.footer { background: #f5f5f8; padding: 12px 28px; font-size: 11px;
          color: #888; border-top: 1px solid #e8e8e8; }
"""


def _wrap_html_email(html_body: str, subject: str, ts_str: str) -> str:
    """Wrap converted Markdown HTML in a CSS-styled email shell."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{subject}</title>
<style>{_EMAIL_CSS}</style>
</head>
<body>
<div class="wrapper">
  <div class="header">
    <h1>📊 Portfolio Intelligence Brief</h1>
    <p>Run: {ts_str} | Auto-generated — analytical observations only</p>
  </div>
  <div class="body">
{html_body}
  </div>
  <div class="footer">
    Not financial advice. Review assumptions before acting on any rebalancing considerations.
  </div>
</div>
</body>
</html>"""


def load_subscribers() -> List[str]:
    """Loads the list of subscriber emails from the configuration."""
    config_path = os.path.join(os.path.dirname(__file__), "..", "..", "config", "subscribers.yml")
    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f)
            return data.get("subscribers", [])
    except Exception as e:
        logger.error(f"Failed to load subscribers.yml: {e}")
        return []


def send_webhook_notification(
    report_path: str,
    ts_str: str,
    subject_hint: Optional[str] = None,
) -> bool:
    """
    Reads the markdown report, converts it to styled HTML, and sends it
    to the configured webhook URL alongside the subscriber list.

    Parameters
    ----------
    report_path : path to the generated .md report file
    ts_str      : run timestamp string (YYYYMMDDTHHMMSS)
    subject_hint: optional override for the email subject line.
                  When provided, replaces the default subject.
                  Useful for including regime / health-score context.
    """
    webhook_url = os.environ.get("WEBHOOK_URL")
    if not webhook_url:
        logger.info("WEBHOOK_URL is not set. Skipping external email notifications.")
        return False

    subscribers = load_subscribers()
    if not subscribers:
        logger.info("No subscribers found. Skipping email notifications.")
        return False

    if not os.path.exists(report_path):
        logger.error(f"Report file {report_path} not found. Cannot send notification.")
        return False

    try:
        with open(report_path, "r") as f:
            md_content = f.read()

        # Convert Markdown → HTML (tables extension improves table rendering)
        html_body = markdown.markdown(md_content, extensions=["tables", "fenced_code"])

        subject = subject_hint or f"eToro Portfolio Agent Run ({ts_str})"
        html_content = _wrap_html_email(html_body, subject, ts_str)

        payload: Dict[str, Any] = {
            "timestamp": ts_str,
            "subject": subject,
            "html_body": html_content,
            "subscribers": subscribers,
        }

        logger.info(f"Dispatching notification to {len(subscribers)} subscribers via Webhook...")
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.status_code in [200, 201, 202, 204]:
            logger.info("Webhook dispatched successfully.")
            return True
        else:
            logger.error(f"Webhook failed with status {response.status_code}: {response.text}")
            return False

    except Exception as e:
        logger.error(f"Failed to send webhook notification: {e}")
        return False
