# Financial Intelligence Radar

Turn SEC disclosures into validated analyst attention.

Source → Validate → Analyze → Investigate

## Overview

**Financial Intelligence Radar** transforms public SEC disclosures into validated, traceable financial observations and deterministic analyst signals, then turns those signals into a practical workflow for company research, peer context, portfolio triage and evidence-based investigation. 

## Business Problem

Financial analysts and financial-data teams deal with large volumes of public-company disclosures and must:
- Source financial data reliably.
- Normalize inconsistent reporting from different entities.
- Validate values and check data quality.
- Identify exceptions and significant divergences.
- Compare periods (YoY, sequential, annual).
- Investigate changes back to their source.
- Maintain source traceability and provenance for compliance.

## Solution

This product is an **evidence-first financial disclosure intelligence and analyst triage workflow**. It automates the extraction, validation, and deterministic comparison of financial data directly from SEC filings, providing an Attention Queue that highlights critical signals for an analyst to investigate further.

## Why SEC Data

SEC EDGAR provides the authoritative source of truth for U.S. public company financials. By ingesting directly from the source and parsing XBRL companyfacts, we eliminate third-party data manipulation, latency, and opaque aggregations, ensuring that every data point can be traced back to a specific legal filing.

## Architecture

\\\mermaid
flowchart TD
    A[SEC EDGAR] -->|Ingestion| B(Raw JSON)
    B --> C(Normalization)
    C --> D(Canonical Observation Layer)
    D --> E(Data Quality)
    E --> F(Analytical Metric Layer)
    F --> G(Signal Engine)
    G --> H(Synthesis)
    H --> I(Peer Context)
    H --> J(Portfolio Context)
    I --> K(Attention Queue)
    J --> K
    K --> L(Research Mode)
    L --> M(SEC Evidence)
\\\

## Data Flow

The system orchestrates a pipeline that maps directly to the analyst workflow:
1. **Fetch**: Retrieves XBRL companyfacts and submissions.
2. **Extract**: Parses us-gaap concepts and applies units.
3. **Normalize**: Maps diverse XBRL concepts (e.g., PaymentsToAcquirePropertyPlantAndEquipment) to canonical metrics (e.g., capital_expenditures).
4. **Evaluate**: Executes deterministic signals against the processed metrics.
5. **Persist**: Stores Observations, Signals, Events, and Peer context in SQLite.

## Analytical Methodology

The analytical metric layer computes ratios and margins strictly when they are mathematically sound and data is present:
- **Profitability:** Gross margin, operating margin, net margin.
- **Cash:** Free cash flow (Operating Cash Flow - Capital Expenditures), cash conversion.
- **Balance Sheet:** Liquidity ratio, debt / operating income, receivables / revenue, inventory / revenue.
- **Growth:** Revenue YoY, Share count YoY.

All analysis enforces strict unit match and appropriate comparison period alignment (~365 days for YoY/Annual, ~90 days for Sequential).

## Data Quality

Data quality is rigorously assessed. Missing values are discarded rather than treated as zero. Quality precedence rules determine the survival of data:
RESTATED / AMENDED > REPORTED > DERIVED > NOT_REPORTED.
Values flagged with COMPARABILITY_SUPPRESSED or CALCULATION_INVALID are actively prevented from contaminating the comparison engine.

## Provenance

Every canonical observation perfectly retains its SEC origin. Analysts can view:
- **CIK** and **Accession Number**
- **SEC URL** and **Form** type
- **Filing date** and **XBRL concept**
- **Period start** and **Period end**

## Signal Engine

Signals are deterministic, versioned, explainable, and reproducible rules. They are not AI hallucinations. The signal engine flags material changes based on analytical thresholds (e.g., GROSS_MARGIN_COMPRESSION, RECEIVABLES_REVENUE_DIVERGENCE), assessing severity and confidence mathematically based on the underlying evidence.

## Peer Methodology

Peer groups define context using a bounded universe configuration. Metrics for a primary company are contextualized against a sector-aware peer reference universe (e.g., comparing AAPL's operating margin to the median of its information technology peers). The alignment ensures peer comparisons enforce a strict 45-day fiscal end boundary constraint.

## Portfolio Context

For triage, the Attention Queue integrates a loaded portfolio. It explicitly maps actionable signals to Portfolio Weight and Exposure, helping analysts focus on the most impactful issues without altering the fundamental financial signal itself.

## Dashboard

The user interface revolves around triage and research:
- **Attention Queue**: Filters and sorts material signals by severity, confidence, and portfolio weight.
- **Research Mode**: Provides a deep-dive environment for a single company, showing historical charts, KPIs, and synthesized narratives mapping directly to SEC evidence.

## Installation

\\\ash
git clone <repo>
cd Financial-Intelligence-Radar
python -m venv .venv
# Activate venv: .venv\Scripts\activate (Windows) or source .venv/bin/activate (Unix)
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
streamlit run app.py
\\\

## SEC User-Agent

The SEC EDGAR API strictly enforces access rates. You must configure a valid User-Agent identifying your application and email before running the application, and the system complies with the 10-requests-per-second pacing limit.
\\\ash
export SEC_USER_AGENT="YourAppName/1.0 (your.email@example.com)"
\\\

## Golden Fixtures

For deterministic testing without network latency, the project maintains compact, repository-stored SEC Golden Fixtures. These are real SEC companyfacts payloads spanning AAPL, MSFT, NVDA, and JPM, enabling end-to-end integration testing of the true SEC data structures.

## Testing

The project maintains comprehensive test coverage across the pipeline:
\\\ash
python -m compileall -q src app.py
python -m pytest -q
\\\

## Known Limitations

- Inference of fiscal quarters from calendar dates is heuristic for companies with non-standard calendars.
- Financial sector logic (e.g. JPM) disables certain corporate signals (like Inventory/Revenue) but currently does not implement a full suite of banking-specific metrics (e.g. Net Interest Margin, CET1).
- The pipeline does not currently parse non-GAAP measures from earnings releases, relying strictly on filed XBRL GAAP concepts.

## Future Extensions

- Implementing industry-specific analytical spines for Real Estate (FFO) and Banking.
- Ingesting text from MD&A sections to correlate deterministically with numerical divergences.
- Expanding the universe to the full Russell 1000.
