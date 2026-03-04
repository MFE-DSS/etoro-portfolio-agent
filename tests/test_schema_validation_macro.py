import pytest
import datetime
from src.macro_regime.io.schemas import validate_macro_regime_state

def test_schema_validation_success():
    payload = {
        "timestamp_utc": "2025-03-04T12:00:00Z",
        "asof_date": "2025-03-04",
        "data_coverage": {
            "all": {
                "start_date": "2000-01-01",
                "end_date": "2025-03-04",
                "missing_days": 0
            }
        },
        "features_summary": {
            "total_features": 10,
            "transforms_applied": ["level", "diff"],
            "lags_applied": ["CPI:15"]
        },
        "model_markov": {
            "p_bull": 0.8,
            "p_bear": 0.2,
            "regime_label": 0,
            "diagnostics": {"loglik": -100, "aic": 200, "bic": 205},
            "params": {"sigma[0]": 0.1}
        },
        "model_events": {
            "p_drawdown_20": 0.1,
            "horizon_days": 63,
            "p_recession": 0.05,
            "coefficients": {},
            "regularization_C": 1.0
        },
        "aggregate": {
            "macro_score_0_100": 85.5,
            "regime_state": "RISK_ON",
            "traffic_light": "GREEN",
            "buy_the_dip_ok": True,
            "recommended_action": "INCREASE_BETA_BUCKET_A"
        },
        "flags": ["OK"]
    }
    
    # Should not raise
    validate_macro_regime_state(payload)
