# eToro Portfolio Agent

A production-grade, repo-based portfolio agent for eToro that fetches portfolio data, normalizes it, and uses Google Gemini to analyze the portfolio decisions.

## Setup Requirements

1. **Python 3.11+**
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Environment Variables / Secrets

This project requires the following environment variables. They must **never** be committed to version control:

- `ETORO_PUBLIC_API_KEY`: API key for accessing eToro public endpoints.
- `ETORO_USER_KEY`: User-specific key for eToro.
- `GOOGLE_API_KEY`: API key for Google Gemini.

### GitHub Actions Setup

In your GitHub repository, go to **Settings > Secrets and variables > Actions** and add the three secrets mentioned above. The scheduled CI/CD weekly workflow will automatically pick them up.

## Running Locally

1. Set your environment variables (e.g., in your shell or via a `.env` file that is ignored by git):
   ```bash
   export ETORO_PUBLIC_API_KEY="your_etoro_api_key"
   export ETORO_USER_KEY="your_etoro_user_key"
   export GEMINI_API_KEY="your_google_api_key"
   ```
2. Run the main pipeline orchestrator:
   ```bash
   python src/main.py
   ```

### Dry Mode Logging and Testing
If the `ETORO_PUBLIC_API_KEY` is completely missing from your environment shell, `src/main.py` will transparently enter **Dry Mode**. It skips making network requests to the eToro API, and instead mocks the input using our local sample payload mapped in `tests/fixtures/snapshot.json`.

This allows for full, comprehensive offline testing of the deterministic V5 metrics engine, history appends, alert condition generation, and JSON outputs. 

## Produced Artifacts & Monitoring (V5)

The pipeline runs deterministically and produces extensive `JSON` output artifacts tracked under the `out/` directory with UTC ISO timestamps. During GitHub Actions runs, these outputs are uploaded as workflow artifact `.zip` bundles.

In addition to normalized `snapshot` and `market_state` representations, the V5 Pipeline exposes:
- **`health_score`**: A strictly deterministic 0-100 penalty score identifying systemic risk mismatches and extreme liquidity dependencies configured in `src/monitoring/health_score.py`.
- **`alerts`**: Real-time rule evaluators testing configuration directives defined via `config/alerts.yml`. If trigger rules are hit, they appear under standard RFC3339 logging.
- **`history.csv`**: Every single main-pipeline orchestrator invocation cleanly adds its derived data vector structure directly tracking changes in macro condition severity alongside optionality depletion paths.
