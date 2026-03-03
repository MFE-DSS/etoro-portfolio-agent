import os
import pytest
from unittest.mock import patch
from src.main import main

@patch("src.collectors.fred_collector.fetch_all_fred")
@patch("src.collectors.market_prices_collector.fetch_all_market_prices")
@patch("src.decision_engine.engine.generate_decisions")
@patch("src.scoring.regime_model.evaluate_regimes_and_scores")
def test_main_dry_run(mock_regime, mock_gen_decisions, mock_fetch_market, mock_fetch_fred, monkeypatch, tmp_path):
    # Ensure no ETORO keys
    monkeypatch.delenv("ETORO_PUBLIC_API_KEY", raising=False)
    monkeypatch.delenv("ETORO_USER_KEY", raising=False)
    
    # Mock data to prevent actual network calls
    mock_fetch_fred.return_value = {"mock_fred": 1}
    mock_fetch_market.return_value = {"mock_market": 1}
    
    mock_regime.return_value = {
        "timestamp": "2026-03-03T10:00:00Z",
        "risk_score": 50,
        "color": "green",
        "indicators": {"liquidity_stress_risk": 0.1, "recession_risk": 0.1},
        "sub_scores": {}
    }
    
    mock_gen_decisions.return_value = {
        "timestamp": "2026-03-03T10:00:00Z",
        "regime_summary": {"risk_score": 50, "color": "green", "key_risks": [], "key_supports": []},
        "portfolio_diagnosis": {"cash_pct": 0, "concentration_flags": [], "correlation_flags": [], "overweights": [], "missing_metadata": []},
        "actions": [],
        "dca_plan_2m": [],
        "alerts": []
    }
    
        # But writing to real 'out' is fine for a local test, it's just generating files.
        # Let's run it and catch the SystemExit if any
        
    try:
        main()
    except SystemExit as e:
        pytest.fail(f"main() exited unexpectedly with code {e.code}")
            
        # Verify it created the V5 artifacts
        assert os.path.exists("out")
        
        # We can't easily assert exact filenames because they have timestamps, 
        # but we can check if the directory has the files.
        files = os.listdir("out")
        assert any("summary_" in f for f in files)
        assert any("alerts_" in f for f in files)
        assert any("decisions_" in f for f in files)
        assert any("portfolio_state_" in f for f in files)
        assert any("market_state_" in f for f in files)
        assert any("logs_" in f for f in files)
        assert any("report_" in f for f in files)
