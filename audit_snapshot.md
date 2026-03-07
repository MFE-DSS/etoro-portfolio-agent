# Audit Snapshot: eToro Portfolio Agent
**Date**: March 7, 2026

## 1. Project Overview & Architecture
The project is a production-grade, repo-based portfolio agent for eToro that fetches portfolio data, normalizes it, and applies multiple layers of quantitative and qualitative analysis.

**Core Layers**:
- **Data Collection & Normalization (`src/collectors/`, `src/normalize.py`)**: Fetches from eToro and FRED, normalizes outputs against strict JSON schemas.
- **V3: Portfolio Overlay Layer (`src/portfolio/`)**: Deterministic layer calculating metric exposures, concentration, and macro fit scores.
- **V5: Macro-Regime Econometrics Layer (`src/macro_regime/`)**: Implements Markov Switching regime models (Hamilton 1989) and penalized Logistic Regression to establish a traffic light system (`GREEN`, `ORANGE`, `RED`) avoiding look-ahead bias and predicting extreme drawdown events.
- **All-Weather Alignment Engine (`src/all_weather_alignment/`)**: A recently added engine aligning portfolio positions against an All-Weather risk-parity framework depending on growth and inflation.
- **LLM Analytics & Monitoring (`src/analyze_llm.py`, `src/monitoring/`)**: Calculates a strictly deterministic `health_score` (0-100) and uses Gemini to analyze portfolio decisions.
- **Publishing & Notification (`src/publish/`, `src/publish/publish.py`)**: Generates a final "Macro Posture Brief (BETA)" report and dispatches it via email or webhook integrations (Zapier).

## 2. Codebase Structure
- `config/`: YAML configurations for macro series, alerts, and fixed assets rules.
- `schemas/`: JSON schemas enforcing strict structural validation for all data boundaries.
- `src/`: Main source code divided by layers (data collection, econometrics, portfolio, LLM, monitoring, publishing).
- `tests/`: Comprehensive test suite leveraging `pytest` with extensive mocked fixtures (`tests/fixtures/snapshot.json`).
- `out/`: Transitory outputs reflecting immutable pipeline state snapshots.

## 3. Test Suite Integrity
**Status**: `PASSED (39/39 tests)`
- **Coverage Highlights**:
  - Determinism tests (`test_determinism_fixed_seed.py`)
  - Pipeline isolation no-lookahead policies (`test_feature_lagging_no_lookahead.py`)
  - Strict schema validations (`test_schema_validation_macro.py`, `test_schema_validation_alignment.py`)
  - Integration layers (`test_v3_portfolio_overlay.py`, `test_v5_dry_mode_pipeline.py`, `test_v6_notifier_email.py`)
- No degradations observed. All core logic flows (including the newer V5 and V6 modules) remain structurally sound and functionally isolated.

## 4. Conclusion
The pipeline is stable, mathematically rigorous, and fully tested. It successfully enforces backward compatibility while integrating advanced probabilistic macros and LLM summarizations.
