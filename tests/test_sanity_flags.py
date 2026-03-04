import pytest
import pandas as pd
from src.macro_regime.rules.signals import compute_signals

def test_sanity_flags_triggered_on_degenerate_probs():
    """
    Test that degenerate probabilities and missing features force a 'HOLD'
    action via the failsafe mechanism.
    """
    df = pd.DataFrame({"QQQ_close": [100.0, 110.0, 105.0]}) # dummy data
    
    # 1. Test nominal (healthy) state
    markov_res_ok = {"p_bull": 0.8, "p_bear": 0.2}
    event_res_ok = {"p_drawdown_20": 0.1, "dd20_positive_rate_train": 0.15}
    ensemble_res_green = {"traffic_light": "GREEN", "regime_state": "RISK_ON"}
    config_dip = {"rules": {"buy_the_dip": {"min_recent_drawdown": 0.01}}} # Make it think it's a dip
    
    out_ok = compute_signals(df, markov_res_ok, event_res_ok, ensemble_res_green, config_dip)
    
    assert out_ok["recommended_action"] == "INCREASE_BETA_BUCKET_A"
    assert out_ok["buy_the_dip_ok"] is True
    assert len(out_ok["signal_flags"]) == 0
    assert out_ok["sanity_checks"]["markov_is_degenerate"] is False
    assert out_ok["sanity_checks"]["events_is_degenerate"] is False

    # 2. Test Markov degenerate (p_bull ~ 0.5)
    markov_res_deg = {"p_bull": 0.505, "p_bear": 0.495}
    out_markov_deg = compute_signals(df, markov_res_deg, event_res_ok, ensemble_res_green, config_dip)
    
    assert out_markov_deg["recommended_action"] == "HOLD"
    assert out_markov_deg["buy_the_dip_ok"] is False
    assert "PROBA_DEGENERATE_MARKOV" in out_markov_deg["signal_flags"]
    assert out_markov_deg["sanity_checks"]["markov_is_degenerate"] is True

    # 3. Test Event degenerate (p_drawdown_20 ~ 0)
    event_res_deg = {"p_drawdown_20": 0.001, "dd20_positive_rate_train": 0.15}
    out_event_deg = compute_signals(df, markov_res_ok, event_res_deg, ensemble_res_green, config_dip)
    
    assert out_event_deg["recommended_action"] == "HOLD"
    assert "PROBA_DEGENERATE_EVENTS" in out_event_deg["signal_flags"]
    assert out_event_deg["sanity_checks"]["events_is_degenerate"] is True
    
    # 4. Test Missing Features Force HOLD (> 3 NA values)
    df_missing = pd.DataFrame({"A": [pd.NA], "B": [pd.NA], "C": [pd.NA], "D": [pd.NA]})
    out_missing = compute_signals(df_missing, markov_res_ok, event_res_ok, ensemble_res_green, config_dip)
    
    assert out_missing["recommended_action"] == "HOLD"
    assert "MISSING_KEY_FEATURES" in out_missing["signal_flags"]
    assert out_missing["sanity_checks"]["missing_key_features_count"] == 4
