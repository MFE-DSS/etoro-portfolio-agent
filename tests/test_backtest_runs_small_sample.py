import pytest
import pandas as pd
import numpy as np

from src.macro_regime.backtest.walk_forward import run_walk_forward
from src.macro_regime.features.build_features import build_features

def test_backtest_runs_small_sample():
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", "2020-12-31")
    
    # We need enough length to satisfy min_train_days for testing, so we fake it.
    raw_data = {
        "QQQ_close": pd.Series(np.exp(np.random.normal(0.001, 0.01, len(dates)).cumsum()), index=dates) * 100,
        "DGS10": pd.Series(np.random.normal(2.0, 0.1, len(dates)), index=dates)
    }
    
    cfg_feats = {
        "features": [
            {"name": "QQQ_close", "transform": "log_return"},
            {"name": "DGS10", "transform": "diff"}
        ],
        "derived": [],
        "qualitative_dummies": []
    }
    
    cfg_mods = {
        "markov_switching": {
            "target_series": "QQQ_close_log_return",
            "num_regimes": 2
        },
        "event_probit": {
            "features": ["DGS10_diff"],
            "horizon_days": 10,
            "drawdown_threshold": -0.05
        },
        "ensemble_scoring": {
            "weights": {"p_bull": 1.0, "p_drawdown_20_inv": 0.0, "p_recession_inv": 0.0}
        }
    }
    
    cfg_bt = {
        "walk_forward": {
            "start_date": "2020-01-01",
            "end_date": "2020-12-31",
            "train_min_period_days": 100, # tiny valid window for test
            "refit_frequency_days": 50,
            "horizon_days": 10
        }
    }
    
    df = build_features(raw_data, cfg_feats, "2020-01-01", "2020-12-31")
    res_df = run_walk_forward(df, cfg_bt, cfg_feats, cfg_mods)
    
    # Just need it to run without crashing, and return a result DF shorter than original by the min train period
    assert not res_df.empty
    assert len(res_df) == len(dates) - 100
    assert "p_bull" in res_df.columns
    assert "macro_score_0_100" in res_df.columns
