"""
Probit/Logit Event probabilities layer.
Predicts Recessions and Drawdowns over a horizon using L2 regularized Logistic Regression.
"""
import pandas as pd
import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from typing import Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def create_event_targets(df: pd.DataFrame, horizon_days: int = 63, drawdown_threshold: float = -0.20) -> pd.DataFrame:
    """
    Creates target variables for the event models.
    DRAWDOWN_20_FWD: 1 if max drawdown over next `horizon_days` exceeds `drawdown_threshold`.
    DRAWDOWN_10_FWD: 1 if max drawdown over next `horizon_days` exceeds -0.10.
    RECESSION_PROXY: Current USREC (lagged proxy applied by features, but here we just use USREC directly if asked to predict it). 
                     Actually, a true forecast would predict USREC shifted backward. For now, assuming user wants probability of *future* DD, and current recession probability from real-time data.
    """
    y_df = pd.DataFrame(index=df.index)
    
    if "QQQ_close" in df.columns:
        # Calculate forward looking max drawdown
        prices = df["QQQ_close"]
        
        # For each day t, look at [t, t + horizon]
        # Max drawdown = min( P_future / P_t - 1 ) for future in horizon
        # To vectorise this efficiently for a rolling forward window:
        roll_min = prices.rolling(window=horizon_days).min()
        # Shift back to align the future window min with today
        forward_min = roll_min.shift(-horizon_days) 
        
        fwd_returns = forward_min / prices - 1.0
        y_df["DRAWDOWN_20_FWD"] = (fwd_returns <= drawdown_threshold).astype(int)
        y_df["DRAWDOWN_10_FWD"] = (fwd_returns <= -0.10).astype(int)
        
        # Nullify the last `horizon_days` rows since we don't know the forward outcome yet
        y_df.loc[y_df.index[-horizon_days]:, "DRAWDOWN_20_FWD"] = np.nan
        y_df.loc[y_df.index[-horizon_days]:, "DRAWDOWN_10_FWD"] = np.nan
        
    if "USREC" in df.columns:
        # Predict if in recession next month (~21 days)
        y_df["RECESSION_FWD"] = df["USREC"].shift(-21)
        
    return y_df

def fit_event_probit(df: pd.DataFrame, config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Fits L2 regularized logistic regressions (probit proxies) for extreme events.
    Uses Goyal/Welch (2008) motivated OOS constraint thinking by aggressively regularizing.
    """
    features = config.get("features", [])
    horizon = config.get("horizon_days", 63)
    thresh = config.get("drawdown_threshold", -0.20)
    C_reg = config.get("C_inverse_regularization", 1.0)
    
    targets = create_event_targets(df, horizon, thresh)
    
    # Feature columns actually present
    X_cols = [c for c in features if c in df.columns]
    
    if not X_cols:
        logger.warning("No valid features found for event model. Returning empty.")
        return {}
        
    out = {
        "horizon_days": horizon,
        "p_drawdown_10": 0.0,
        "p_drawdown_20": 0.0,
        "p_drawdown_composite": 0.0,
        "p_recession": 0.0,
        "dd20_positive_rate_train": 0.0,
        "coefficients": {},
        "regularization_C": C_reg
    }
    
    X_raw = df[X_cols]
    scaler = StandardScaler()
    
    # 1. Fit Drawdown prediction
    if "DRAWDOWN_20_FWD" in targets.columns:
        # Drop rows where target is NA (the last `horizon` days) or features are NA
        mask = targets["DRAWDOWN_20_FWD"].notna() & X_raw.notna().all(axis=1)
        X_train = X_raw[mask]
        y_train = targets.loc[mask, "DRAWDOWN_20_FWD"]
        
        if len(X_train) > 252 and y_train.sum() > 5: # Need enough minority class
            X_scaled = scaler.fit_transform(X_train)
            model_dd = LogisticRegression(penalty='l2', C=C_reg, solver='lbfgs', max_iter=1000)
            model_dd.fit(X_scaled, y_train)
            
            # Predict for today (last row in df, may contain NA so we fill)
            X_today = X_raw.iloc[[-1]].copy()
            # If today has NA features, standard fill is 0 (mean) given scaler
            X_today.fillna(X_raw.mean(), inplace=True)
            X_today_scaled = scaler.transform(X_today)
            
            p_dd = model_dd.predict_proba(X_today_scaled)[0, 1]
            out["p_drawdown_20"] = float(p_dd)
            out["dd20_positive_rate_train"] = float(y_train.mean())
            
            out["coefficients"]["drawdown_20"] = {
                feat: float(coef) for feat, coef in zip(X_cols, model_dd.coef_[0])
            }
        else:
            logger.warning("Insufficient data or positive cases to fit Drawdown Event model.")
            
    # 2. Fit Drawdown 10 prediction
    if "DRAWDOWN_10_FWD" in targets.columns:
        mask = targets["DRAWDOWN_10_FWD"].notna() & X_raw.notna().all(axis=1)
        X_train = X_raw[mask]
        y_train = targets.loc[mask, "DRAWDOWN_10_FWD"]
        
        if len(X_train) > 252 and y_train.sum() > 5:
            X_scaled = scaler.fit_transform(X_train)
            model_dd10 = LogisticRegression(penalty='l2', C=C_reg, solver='lbfgs', max_iter=1000)
            model_dd10.fit(X_scaled, y_train)
            
            X_today = X_raw.iloc[[-1]].copy()
            X_today.fillna(X_raw.mean(), inplace=True)
            X_today_scaled = scaler.transform(X_today)
            
            p_dd10 = model_dd10.predict_proba(X_today_scaled)[0, 1]
            out["p_drawdown_10"] = float(p_dd10)
            
            out["coefficients"]["drawdown_10"] = {
                feat: float(coef) for feat, coef in zip(X_cols, model_dd10.coef_[0])
            }

    out["p_drawdown_composite"] = 0.7 * out["p_drawdown_20"] + 0.3 * out["p_drawdown_10"]

    # 3. Fit Recession prediction (if available)
    if "RECESSION_FWD" in targets.columns:
        mask = targets["RECESSION_FWD"].notna() & X_raw.notna().all(axis=1)
        X_train = X_raw[mask]
        y_train = targets.loc[mask, "RECESSION_FWD"]
        
        if len(X_train) > 252 and y_train.sum() > 5:
            X_scaled = scaler.fit_transform(X_train)
            model_rec = LogisticRegression(penalty='l2', C=C_reg, solver='lbfgs', max_iter=1000)
            model_rec.fit(X_scaled, y_train)
            
            X_today = X_raw.iloc[[-1]].copy()
            X_today.fillna(X_raw.mean(), inplace=True)
            X_today_scaled = scaler.transform(X_today)
            
            p_rec = model_rec.predict_proba(X_today_scaled)[0, 1]
            out["p_recession"] = float(p_rec)
            
            out["coefficients"]["recession"] = {
                feat: float(coef) for feat, coef in zip(X_cols, model_rec.coef_[0])
            }
            
    return out
