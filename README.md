# Financial Intelligence Radar

An evidence-first, zero-cost SEC disclosure intelligence and analyst-triage application for institutional and fundamental equity research.

> **Disclaimer**: Financial Intelligence Radar is strictly an analyst-triage and disclosure-verification tool. It does **not** provide investment advice, trading recommendations, price forecasts, or automated financial decision-making.

---

### Deployment Status
- **Source Repository:** [https://github.com/Rishika667/Financial-Intelligence-Radar](https://github.com/Rishika667/Financial-Intelligence-Radar)
- **Hosted Streamlit Application:** *Deployment pending* (Follow the step-by-step instructions in [docs/STREAMLIT_DEPLOYMENT.md](docs/STREAMLIT_DEPLOYMENT.md) to launch on Streamlit Community Cloud)

---

## 1. Product Overview

Financial Intelligence Radar extracts, normalizes, and analyzes official SEC EDGAR disclosures (10-K, 10-Q, 8-K) to surface material financial shifts, margin compression, cash flow divergence, and executive turnover.

### Key Capabilities

- **100% SEC Authoritative Data**: Ingests directly from public SEC EDGAR APIs (Submissions and Company Facts XBRL). Zero paid API keys, zero third-party data aggregators.
- **Full S&P 500 Constituent Universe**: 503 constituents mapped with authoritative 10-digit CIKs, sectors, and sub-industries (`config/sp500_universe_2026.json`, snapshot date: 2026-10-13, sourced from public Wikipedia constituent data cross-referenced with SEC EDGAR). Representative 51-company baseline preserved as an explicit compatibility mode (`config/sp500_representative_51_2026.json`).
- **Research Mode for All Supported Companies**: Search and analyze any company in the S&P 500 universe. Companies not yet ingested display a clean `NOT-YET-LOADED` state with on-demand single-company SEC fetching.
- **Persistent Analyst Reviews**: Track triage status for surfaced signals (`NEW`, `ACKNOWLEDGED`, `UNDER_REVIEW`, `DISMISSED`, `EXPECTED`, `RESOLVED`) with persistent reviewer notes and deterministic alert fingerprints stored in SQLite.
- **Data Quality & Refresh Monitoring**: Dedicated tab featuring universe-wide readiness breakdowns (`READY`, `PARTIAL`, `NOT_READY`), persistent refresh audit logs, metric-level data availability diagnostics, peer coverage integrity checks, and regulatory freshness guidelines.
- **10-Company Multi-Period Golden Fixtures**: Offline test fixtures for 10 prominent companies across diverse sectors (AAPL, MSFT, NVDA, JPM, AMZN, GOOGL, META, TSLA, JNJ, XOM) enabling 100% offline, deterministic CI testing.
- **Strict Data Quality Precedence**: `AMENDED` / `RESTATED` > `REPORTED` > `DERIVED`. Never turns missing disclosure facts into zero.
- **Fiscal-Period Reconstruction**: Enforces strict quarter-vs-quarter and annual-vs-annual comparisons. Standalone quarters are derived from YTD disclosures with exact math, never mixed with annual or YTD durations.
- **Full Audit Lineage**: Every observation, metric, and signal links directly back to the accession number, filing date, and official SEC filing URL.

---

## 2. Quick Start

### Prerequisites
- Python 3.11+
- Git

### Local Setup

```bash
# 1. Clone repository
git clone https://github.com/Rishika667/Financial-Intelligence-Radar.git
cd Financial-Intelligence-Radar

# 2. Create virtual environment
python -m venv .venv

# On Linux/macOS:
source .venv/bin/activate
# On Windows PowerShell:
.venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Configure required SEC User-Agent header
# SEC EDGAR requires a User-Agent in the format: "Sample Company Name AdminContact@<sample company domain>.com"
# On Linux/macOS:
export SEC_USER_AGENT="AnalystResearch analyst@example.com"
# On Windows PowerShell:
$env:SEC_USER_AGENT = "AnalystResearch analyst@example.com"

# 5. Launch the Streamlit application
streamlit run app.py
```

### GitHub Codespaces Setup

The repository includes a ready-to-use `.devcontainer/devcontainer.json` environment:
1. Open the repository in GitHub Codespaces.
2. In the Codespace terminal or repository environment secrets, set `SEC_USER_AGENT`:
   ```bash
   export SEC_USER_AGENT="AnalystResearch analyst@example.com"
   ```
3. Run `streamlit run app.py` and open the forwarded port (default: 8501).

---

## 3. Running Automated Tests

Deterministic offline tests execute against local SEC golden fixtures without requiring network access or external credentials:

```bash
pytest
```

---

## 4. Application Architecture

```
Financial Intelligence Radar
├── app.py                                # Streamlit multi-tab user interface
├── config/
│   ├── sp500_universe_2026.json          # Full 503-constituent S&P 500 snapshot
│   └── sp500_representative_51_2026.json # 51-company representative baseline
├── src/financial_radar/
│   ├── core.py                           # SEC EDGAR client, rate limiting, data ingestion
│   ├── models.py                         # Domain models (Observation, Signal, DataQuality)
│   ├── store.py                          # SQLite schema, WAL mode, migrations, analyst reviews
│   ├── pipeline.py                       # Fiscal reconstruction, metric derivations, signals
│   ├── peers.py                          # Curated peer groups, peer-relative context
│   └── portfolio.py                      # Portfolio CSV import, validation, exposure matching
└── tests/
    ├── fixtures/                         # Multi-period SEC facts & submissions for 10 companies
    └── test_*.py                         # Comprehensive test suites
```

---

## 5. Scope & Known Limitations

1. **Zero Predictive Claims**: The system detects historical disclosure changes; it does not model future stock prices or provide trading recommendations.
2. **SEC Rate Limiting**: SEC EDGAR enforces a maximum rate of 10 requests per second. The application strictly adheres to this limit.
3. **Specialized Banking Metrics**: Does not model bank-specific regulatory ratios (e.g., Net Interest Margin, CET1 capital ratios, loan-loss provisioning semantics).
4. **Deterministic Rules Only**: All signals are generated via deterministic accounting calculations and rule-based thresholds; no probabilistic LLM/AI narrative generation is used.
5. **Freshness Guidance (Documented Standard)**: The application documents regulatory filing deadlines (10-Q within 40-45 days, 10-K within 60-90 days, >180 days aging expectation); automated calculation of stale flags is documented guidance rather than an automated calculation engine.
6. **Constituent Provenance**: The 503-constituent universe is derived from a recorded public snapshot (Wikipedia S&P 500 constituent table cross-referenced with SEC EDGAR CIKs) as of 2026-10-13, not an official direct subscription feed from S&P Dow Jones Indices.

