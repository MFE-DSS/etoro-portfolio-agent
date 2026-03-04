# V5 Macro-Regime Econometrics Layer

> **Note:** The final output of the V5 pipeline is the "Macro Posture Brief (BETA)". This report focuses solely on macro-regime signalling and action sets. Portfolio diagnostics and holding details have been intentionally removed by design in BETA.
This document outlines the architecture and methodologies of the V5 Macro-Regime Econometrics Layer integrated into the eToro Portfolio Agent.

## 1. Overview
The V5 macro layer introduces state-of-the-art out-of-sample predictability techniques to produce rigorous market regime flags and extreme event probabilities (recessions, drawdowns). Unlike naive regression models, this layer emphasizes robust ensembling, constraints, and strict lack of look-ahead bias, making it a reliable signal for live trading systems.

## 2. Methodology & Models

### 2.1 Stationarity & Feature Engineering
Macroeconomic variables (Non-farm payrolls, CPI, Term Spread, VIX) arrive at varying frequencies (daily, weekly, monthly).
- The pipeline utilizes a strict `release_lag_days` policy. Observations are forward-filled in the calendar *only after* their realistic proxy release date has passed.
- **CRITICAL:** `release_lag_days` are interpreted as **BUSINESS DAYS** (not calendar days). This ensures that weekend/holiday effects do not create inconsistent effective lags, keeping the "as-of" availability completely stable.
- Stationarity transforms (Year-over-Year %, 52-week Z-scores, differences) are applied, followed by rolling empirical winsorization to curb outlier dominance.

### 2.2 Markov Switching Regime Model
Based on the foundational work by Hamilton (1989), the system fits a Markov Switching model (via `statsmodels`) on the target index (QQQ log returns). 
- We configure a 2-regime process, prioritizing Mean & Variance switching by default. This is more informative for macro swing regimes than variance-only switching.
- Produces explicit `bull_idx` and `bear_idx` states by computing robust weighted means and variances using smoothed probabilities, removing ambiguity over regime assignments.

### 2.3 Event Models (L2 Logistic Regression)
Predicting extreme events like a forward 20% drawdown requires handling sparse targets.
- Uses **L2 Regularized Logistic Regression** (often colloquially referred to as a probit proxy, though strictly it is Logistic) trained on lagged macro features.
- Generates `p_drawdown_20` (probability of a >20% max DD in the next 63 days) and `p_recession`.
- Following Campbell & Thompson (2008) and Goyal & Welch (2008), we impose heavy constraints (L2 regularization) to prevent the feature set from overfitting historical noise.

### 2.4 Score Aggregation & Rules
The model outputs are combined into a $[0, 100]$ score using fixed weights mimicking forecast combination theory (Rapach, Strauss, Zhou 2010), leading to a Traffic Light System (`GREEN`, `ORANGE`, `RED`).
- **"Buy the Dip" Signal:** Triggers when the recent local peak vs current price exhibits a threshold drawdown (e.g., >5%), BUT `p_recession` and `p_drawdown_20` remain benign, and the traffic light isn't strictly red.

## 3. Usage & Integration

The output `macro_regime_state_<ts>.json` is consumed upstream by the V3 Portfolio Overlay.

**Daily execution:**
```bash
python scripts/run_macro_regime.py --asof $(date -u +"%Y-%m-%d") --data-dir data/ --out-dir out/
```

**Walk-forward testing:**
```bash
python scripts/run_backtest_v5.py --data-dir data/
```
*(Produces predictions, equity curves, and plots inside `backtests/v5/`)*

## 4. Why this matters
Traditional regression overfits the equity premium historically but collapses out of sample. Framing the problem as *Regime Identification* plus *Extreme Event Avoidance*, and combining constraints (L2) with structural shifts (Markov Switching), yields a much more stable set of gating rules for the portfolio overlay.
