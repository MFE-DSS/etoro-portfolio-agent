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
            "bull_idx": 0,
            "bear_idx": 1,
            "regime_most_likely_idx": 0,
            "most_likely_is_bull": True,
            "diagnostics": {"loglik": -100, "aic": 200, "bic": 205},
            "params": {"sigma[0]": 0.1},
            "regime_stats": {
                "means": [0.01, -0.01],
                "variances": [0.001, 0.005],
                "mean_variance_switching": True,
                "switching_variance": True
            }
        },
        "model_events": {
            "p_drawdown_10": 0.2,
            "p_drawdown_20": 0.1,
            "p_drawdown_composite": 0.13,
            "horizon_days": 63,
            "p_recession": 0.05,
            "dd20_positive_rate_train": 0.15,
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
        "sanity_checks": {
            "markov_probs_sum": 1.0,
            "markov_is_degenerate": False,
            "events_is_degenerate": False,
            "dd20_positive_rate_train": 0.15,
            "missing_key_features_count": 0
        },
        "flags": ["OK"]
    }
    
    # Should not raise
    validate_macro_regime_state(payload)
