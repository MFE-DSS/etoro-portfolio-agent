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
   export GOOGLE_API_KEY="your_google_api_key"
   ```
2. Run the main pipeline orchestrator:
   ```bash
   python src/main.py
   ```

## Produced Artifacts

The pipeline runs deterministically and produces JSON output files in the `out/` directory with UTC timestamps (e.g., `snapshot_20260302_080000.json`, `decisions_20260302_080000.json`). During GitHub Actions runs, these outputs are uploaded as workflow artifacts.
