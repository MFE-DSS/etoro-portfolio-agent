import pytest
import pandas as pd
import numpy as np

from src.macro_regime.models.markov_switching import fit_markov_model

def get_dummy_data():
    np.random.seed(42)
    dates = pd.bdate_range("2020-01-01", "2024-01-01")
    # Simulate a two regime series.
    # First half low vol, second half high vol
    n1 = len(dates) // 2
    n2 = len(dates) - n1
    rets = np.concatenate([
        np.random.normal(0.001, 0.01, n1),
        np.random.normal(-0.001, 0.03, n2)
    ])
    df = pd.DataFrame({"TARGET": rets}, index=dates)
    return df

def test_markov_model_determinism():
    """Ensure identical data yields identical probabilities."""
    df = get_dummy_data()
    
    config = {
        "target_series": "TARGET",
        "num_regimes": 2,
        "model_type": "variance_switching",
        "max_iterations": 50,
        "search_method": "ncg"
    }
    
    res1, _ = fit_markov_model(df, config)
    res2, _ = fit_markov_model(df.copy(), config)
    
    # Check that they both fitted
    assert res1
    assert res2
    
    assert np.isclose(res1["p_bull"], res2["p_bull"], atol=1e-5)
    assert np.isclose(res1["p_bear"], res2["p_bear"], atol=1e-5)
    assert res1["regime_most_likely_idx"] == res2["regime_most_likely_idx"]
