import pytest
from unittest.mock import patch, MagicMock
from src.decision_engine.engine import generate_decisions, build_fallback_decisions, strip_invalid_tickers
import json
import os

@pytest.fixture
def mock_inputs():
    snapshot = {"cash_pct": 0.1, "positions": [{"ticker": "AAPL", "weight_pct": 0.4}]}
    market_state = {"risk_score": 50, "color": "orange", "indicators": {}}
    portfolio_state = {"positions": [{"ticker": "AAPL", "weight_pct": 0.4}], "risk_overlay": {"flags": []}}
    return snapshot, market_state, portfolio_state

def test_fallback_decisions(mock_inputs):
    snapshot, market_state, portfolio_state = mock_inputs
    fallback = build_fallback_decisions(snapshot, market_state, portfolio_state, "Test Message")
    
    assert fallback["regime_summary"]["risk_score"] == 50
    assert fallback["regime_summary"]["color"] == "orange"
    assert len(fallback["actions"]) > 0
    assert fallback["actions"][0]["action"] == "HOLD"
    assert fallback["alerts"][0]["name"] == "Engine Fallback"
    
def test_strip_invalid_tickers():
    invalid_decisions = {
        "actions": [
            {"ticker": "AAPL", "action": "HOLD"},
            {"ticker": "FAKE_TICKER", "action": "ADD"}
        ],
        "dca_plan_2m": [
            {
                "week": 1,
                "targets": [
                    {"ticker": "AAPL", "pct": 0.5},
                    {"ticker": "FAKE_TICKER2", "pct": 0.5}
                ]
            }
        ]
    }
    
    valid_tickers = ["AAPL", "MSFT"]
    cleaned = strip_invalid_tickers(invalid_decisions, valid_tickers)
    
    assert len(cleaned["actions"]) == 1
    assert cleaned["actions"][0]["ticker"] == "AAPL"
    assert len(cleaned["dca_plan_2m"][0]["targets"]) == 1
    assert cleaned["dca_plan_2m"][0]["targets"][0]["ticker"] == "AAPL"

@patch('src.decision_engine.engine.genai.Client')
def test_generate_decisions_valid_json(mock_client_class, mock_inputs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    snapshot, market_state, portfolio_state = mock_inputs
    valid_tickers = ["AAPL"]
    
    # Mock LLM returning valid JSON
    mock_client = MagicMock()
    mock_chats = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    valid_json_str = json.dumps({
        "timestamp": "2026-03-03T10:00:00Z",
        "regime_summary": {
            "risk_score": 60,
            "color": "green",
            "key_risks": ["mock risk"],
            "key_supports": ["mock support"]
        },
        "portfolio_diagnosis": {
            "cash_pct": 0.1,
            "concentration_flags": ["none"],
            "correlation_flags": ["none"],
            "overweights": [],
            "missing_metadata": []
        },
        "actions": [
            {"ticker": "AAPL", "action": "HOLD", "priority": 1, "rationale": "Holding", "max_change_pct": 0.0}
        ],
        "dca_plan_2m": [
            {
                "week": 1,
                "allocation_pct_of_cash": 0.1,
                "targets": [{"ticker": "AAPL", "pct": 1.0}],
                "conditions": ["none"]
            }
        ],
        "alerts": []
    })
    
    mock_response.text = f"```json\n{valid_json_str}\n```"
    mock_chat.send_message.return_value = mock_response
    mock_chats.create.return_value = mock_chat
    mock_client.chats = mock_chats
    mock_client_class.return_value = mock_client
    
    decisions = generate_decisions(snapshot, market_state, portfolio_state, valid_tickers)
    assert decisions["regime_summary"]["color"] == "green"
    assert len(decisions["actions"]) == 1

@patch('src.decision_engine.engine.genai.Client')
def test_generate_decisions_trigger_fallback_on_garbage(mock_client_class, mock_inputs, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake_key")
    snapshot, market_state, portfolio_state = mock_inputs
    valid_tickers = ["AAPL"]
    
    mock_client = MagicMock()
    mock_chats = MagicMock()
    mock_chat = MagicMock()
    mock_response = MagicMock()
    
    # Mock LLM returning garbage text both times
    mock_response.text = "This is not json."
    mock_chat.send_message.return_value = mock_response
    mock_chats.create.return_value = mock_chat
    mock_client.chats = mock_chats
    mock_client_class.return_value = mock_client
    
    decisions = generate_decisions(snapshot, market_state, portfolio_state, valid_tickers)
    
    # Should engage fallback
    assert len(decisions["alerts"]) > 0
    assert decisions["alerts"][0]["name"] == "Engine Fallback"
    assert "Expecting value" in decisions["alerts"][0]["meaning"] or "decode" in decisions["alerts"][0]["meaning"]
