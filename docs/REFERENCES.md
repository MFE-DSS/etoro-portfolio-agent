# Scientific Underpinnings of the V5 Macro-Regime Layer

The V5 layer design choices enforce rigorous quantitative constraints based on the following seminal papers in financial econometrics:

1. **Hamilton, J. D. (1989). "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle."**
   _Econometrica_, 57(2), 357-384.
   *Application:* The foundation of the `markov_switching.py` module. Modeling the business cycle and market volatility as unobserved discrete states with transition probabilities naturally fits the boom/bust nature of asset prices.

2. **Goyal, A., & Welch, I. (2008). "A Comprehensive Look at The Empirical Performance of Equity Premium Prediction."**
   _The Review of Financial Studies_, 21(4), 1455-1508.
   *Application:* Highlights that most unconstrained single-variable OLS macro models fail terribly Out-Of-Sample. This motivated our strict `release_lag_days` pipeline, Heavy L2 Regularization in the Probit model, and abandoning raw return forecasting in favor of categorical event risk modeling.

3. **Campbell, J. Y., & Thompson, S. B. (2008). "Predicting Excess Stock Returns Out of Sample: Can Anything Beat the Historical Average?"**
   _The Review of Financial Studies_, 21(4), 1509-1531.
   *Application:* Demonstrated that mild restrictions (e.g. bounding coefficients or forecasts) drastically improve OOS performance. Our traffic light thresholds and risk limits embody this "restricted bounds" philosophy.

4. **Rapach, D. E., Strauss, J. K., & Zhou, G. (2010). "Out-of-Sample Equity Premium Prediction: Combination Forecasts and Links to the Real Economy."**
   _The Review of Financial Studies_, 23(2), 821-862.
   *Application:* Shows that combining relatively weak individual forecasts yields a statistically superior meta-forecast. Our `ensemble_scoring` weighting scheme pools the Markov Regime unobserved state probabilities with the L2-regularized Logistic Regression Event probabilities.
