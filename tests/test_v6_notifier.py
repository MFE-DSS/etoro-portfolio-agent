from unittest.mock import patch, mock_open
import os
import pytest
from src.publish.notifier import send_webhook_notification, load_subscribers

@patch("src.publish.notifier.open", new_callable=mock_open, read_data="subscribers:\n  - test@example.com")
def test_load_subscribers(mock_file):
    subs = load_subscribers()
    assert len(subs) == 1
    assert subs[0] == "test@example.com"

@patch("src.publish.notifier.requests.post")
@patch("src.publish.notifier.load_subscribers")
@patch("src.publish.notifier.os.path.exists")
@patch("src.publish.notifier.open", new_callable=mock_open, read_data="# Fake MD\nHello")
def test_send_webhook_success(mock_file, mock_exists, mock_load_subs, mock_post, monkeypatch):
    monkeypatch.setenv("WEBHOOK_URL", "https://fake.webhook.com")
    
    # Configure mocks
    mock_exists.return_value = True
    mock_load_subs.return_value = ["test1@email.com", "test2@email.com"]
    
    # Mock response
    mock_response = mock_post.return_value
    mock_response.status_code = 200
    
    result = send_webhook_notification("fake/path.md", "20260303_120000")
    
    assert result is True
    assert mock_post.call_count == 1
    
    # Verify the payload structure that was sent
    call_args = mock_post.call_args[1]
    assert "timeout" in call_args
    
    payload = call_args["json"]
    # CSS wrapper is present — content is still inside html_body
    assert "<h1>Fake MD</h1>" in payload["html_body"]
    assert "<p>Hello</p>" in payload["html_body"]
    assert "<!DOCTYPE html>" in payload["html_body"], "Expected CSS-wrapped HTML"
    assert len(payload["subscribers"]) == 2
    # Default subject (no subject_hint) keeps legacy format
    assert payload["subject"] == "eToro Portfolio Agent Run (20260303_120000)"


@patch("src.publish.notifier.requests.post")
@patch("src.publish.notifier.load_subscribers")
@patch("src.publish.notifier.os.path.exists")
@patch("src.publish.notifier.open", new_callable=mock_open, read_data="# Brief\nSummary")
def test_send_webhook_subject_hint(mock_file, mock_exists, mock_load_subs, mock_post, monkeypatch):
    """subject_hint overrides the default email subject."""
    monkeypatch.setenv("WEBHOOK_URL", "https://fake.webhook.com")
    mock_exists.return_value = True
    mock_load_subs.return_value = ["test@email.com"]
    mock_post.return_value.status_code = 200

    hint = "Portfolio Brief — Goldilocks | Health 85/100 (GREEN) | 2026-03-08"
    result = send_webhook_notification("fake/path.md", "20260308T120000", subject_hint=hint)

    assert result is True
    payload = mock_post.call_args[1]["json"]
    assert payload["subject"] == hint

@patch("src.publish.notifier.requests.post")
def test_send_webhook_missing_url(mock_post, monkeypatch):
    monkeypatch.delenv("WEBHOOK_URL", raising=False)
    result = send_webhook_notification("fake/path.md", "20260303_120000")
    assert result is False
    assert mock_post.call_count == 0
