# Streamlit Community Cloud Deployment Guide

This guide describes how to deploy the **Financial Intelligence Radar** application to [Streamlit Community Cloud](https://share.streamlit.io).

---

## 1. Prerequisites

1. A GitHub account with access to the [`Rishika667/Financial-Intelligence-Radar`](https://github.com/Rishika667/Financial-Intelligence-Radar) repository.
2. A free [Streamlit Community Cloud account](https://share.streamlit.io) connected to your GitHub account.
3. A valid user-agent string identifying yourself to the SEC EDGAR API in compliance with [SEC Fair Access rules](https://www.sec.gov/os/accessing-edgar-data).

---

## 2. Deployment Settings

1. Sign in to [share.streamlit.io](https://share.streamlit.io) and click **New app**.
2. Configure the deployment parameters:
   - **Repository:** `Rishika667/Financial-Intelligence-Radar`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL (optional):** Choose a custom subdomain if available (e.g., `financial-intelligence-radar`).
3. Click **Advanced settings...**:
   - **Python version:** Select **3.11**.
   - **Secrets:** Configure the application secrets described below.

---

## 3. Configuring Streamlit Secrets

In the **Secrets** text box under Advanced Settings (or under App Settings -> Secrets after creation), paste the following configuration template:

```toml
# SEC EDGAR Access Identity (Mandatory for live SEC ingestion)
# Replace placeholder with your real name and contact email per SEC Fair Access policy.
SEC_USER_AGENT = "Your Name your.email@example.com"

# Public Demo Mode Safeguard
# Keeps visitor-specific portfolio uploads and review notes isolated to their browser session.
PUBLIC_DEMO_MODE = "true"
```

> [!WARNING]
> Never commit real emails or `.streamlit/secrets.toml` to Git. The `.streamlit/` directory is excluded by `.gitignore`.

---

## 4. Dependency Installation Mechanics

- Streamlit Community Cloud automatically detects the root-level [`requirements.txt`](file:///c:/Users/HP/.gemini/antigravity/scratch/Financial-Intelligence-Radar/requirements.txt).
- The file contains `-e .`, which instructs `pip` to install the package and its runtime dependencies declared in `pyproject.toml` (`requests>=2.31`, `pandas>=2.0`, `streamlit>=1.30`, `plotly>=5.18`).
- Development and test packages (such as `pytest`) are excluded from the deployment environment.

---

## 5. Ephemeral Storage Notice

Streamlit Community Cloud operates on ephemeral container instances:
- The local SQLite database (`financial_radar.sqlite`) is created at runtime and resets upon container recreation or app reboot.
- Cached SEC JSON artifacts (`data/raw/`) are stored on container disk and are re-fetched as needed.
- In `PUBLIC_DEMO_MODE`, visitor portfolio uploads and analyst review notes remain in browser memory (`st.session_state`) during their session.
- Do not treat the Community Cloud filesystem as a durable archive for proprietary customer data.

---

## 6. What Happens When Secrets Are Absent

If `SEC_USER_AGENT` is not yet configured:
1. The app displays an informational notice at the top:
   > ⚠️ **Live SEC Ingestion Unavailable:** `SEC_USER_AGENT` is not configured.
2. The entire dashboard remains navigable in read-only analysis mode on pre-cached disclosure fixtures.
3. Ingestion buttons display clear warning messages rather than throwing unhandled exceptions.
4. No automatic bulk SEC polling is executed on page load.

---

## 7. Running the First Live Smoke Test

Once the application deploys:
1. Open the hosted Streamlit URL.
2. Navigate to **Setup & Preflight**:
   - Click **Test SEC Connectivity**.
   - Verify that all three SEC endpoints (SEC Homepage, Submissions, XBRL Company Facts) report green checkmarks.
3. Navigate to **Research Mode**:
   - Select **AAPL** or another supported company from the 503-company universe.
   - Click **Fetch SEC Disclosure Data for AAPL**.
   - Verify that SEC filings, executive metrics, and historical trend charts populate cleanly.

---

## 8. Troubleshooting

| Issue | Cause | Resolution |
| :--- | :--- | :--- |
| **Build error: module financial_radar not found** | Root `requirements.txt` missing or not run. | Ensure `requirements.txt` contains `-e .` and Python 3.11 is selected. |
| **SEC Preflight: User-Agent error** | Missing or invalid user-agent format. | Ensure `SEC_USER_AGENT` includes an `@` email address in Streamlit secrets. |
| **HTTP 429 Too Many Requests** | Transient SEC EDGAR rate limit hit. | Built-in exponential backoff handles brief limits. Avoid rapid parallel refreshes. |
| **Portfolio wiped after refresh** | Expected behavior in `PUBLIC_DEMO_MODE`. | In demo mode, visitor data is session-scoped to protect privacy across concurrent users. |
