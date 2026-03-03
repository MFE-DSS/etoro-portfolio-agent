import os
import yaml
import markdown
import requests
import logging
from typing import List, Dict, Any

logger = logging.getLogger(__name__)

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

def send_webhook_notification(report_path: str, ts_str: str) -> bool:
    """
    Reads the markdown report, converts it to HTML, and sends it 
    to the configured webhook URL alongside the subscriber list.
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
            
        # Convert Markdown to HTML for beautiful email rendering
        html_content = markdown.markdown(md_content)
        
        payload: Dict[str, Any] = {
            "timestamp": ts_str,
            "subject": f"eToro Portfolio Agent Run ({ts_str})",
            "html_body": html_content,
            "subscribers": subscribers
        }
        
        # Fire the webhook
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
