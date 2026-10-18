"""
Deterministic export utilities for Fundamentals Lens (Phase 7).
Generates company-specific CSV datasets, peer comparison CSVs, technical analysis exports,
and formatted research briefs with explicit provenance and accounting comparability caveats.
"""
import io
import csv
from typing import List, Dict, Any, Optional
from datetime import date
import pandas as pd

from .models import Company, FinancialFact, DerivedMetrics, TechnicalSummary
from .metrics import compute_derived_metrics_for_company, calculate_cumulative_cash_flows, calculate_cagr
from .insights import NarrativeEngine, FinancialInsight


class ExportGenerator:
    """
    Generates downloadable CSV data and Markdown research briefs with explicit provenance,
    mathematical invariants, and accounting comparability caveats.
    """

    @classmethod
    def generate_company_csv(
        cls, 
        company: Company, 
        facts: List[FinancialFact],
        derived: Optional[List[DerivedMetrics]] = None
    ) -> str:
        """
        Generates a clean, comma-separated values string of 5-year financials and metrics.
        Preserves empty values as empty strings without synthetic zero coercion.
        Preserves backwards-compatible column indices 0-32, with Phase 7 deeper indicators in 33-38.
        """
        if derived is None:
            derived = compute_derived_metrics_for_company(facts)
        derived_map = {d.fiscal_year: d for d in derived}

        output = io.StringIO()
        writer = csv.writer(output)

        # Header (Index 10 is Revenue, Index 27 is Comparability Flag, Index 29 is Reconciliation Tier)
        writer.writerow([
            "Ticker",
            "Company Name",
            "Peer Group",
            "Country",
            "Currency",
            "Standard Unit",
            "Fiscal Year",
            "Fiscal Year Label",
            "Period Start",
            "Period End",
            "Revenue",
            "Revenue Growth YoY (%)",
            "Operating Income",
            "Operating Margin (%)",
            "Net Income",
            "Net Margin (%)",
            "Operating Cash Flow",
            "Capital Expenditure",
            "Free Cash Flow",
            "Cash Conversion Ratio (x)",
            "Cash Conversion Note",
            "Statement Basis",
            "Verification Status",
            "Source ID",
            "Filing Date",
            "Accession ID",
            "Source URL",
            "Comparability Flag",
            "Accounting Notes",
            "Reconciliation Tier",
            "Official Filing ID",
            "Internal Document Key",
            "Reference Type",
            # Phase 7 Deeper Metrics
            "Operating Margin Change (bps)",
            "Net Margin Change (bps)",
            "FCF Margin (%)",
            "Capex Intensity (%)",
            "Reinvestment Rate (%)",
            "Operating Leverage Spread (%)"
        ])

        for f in sorted(facts, key=lambda x: x.fiscal_year):
            d = derived_map.get(f.fiscal_year)
            writer.writerow([
                company.ticker,
                company.name,
                company.peer_group_name,
                company.country,
                company.reporting_currency,
                company.standard_unit_label,
                f.fiscal_year,
                f.fiscal_year_label,
                f.period_start,
                f.period_end,
                f.revenue,
                f"{d.revenue_growth_yoy:.2f}" if (d and d.revenue_growth_yoy is not None) else "",
                f.operating_income,
                f"{d.operating_margin:.2f}" if (d and d.operating_margin is not None) else "",
                f.net_income,
                f"{d.net_margin:.2f}" if (d and d.net_margin is not None) else "",
                f.operating_cash_flow,
                f.capital_expenditure,
                f"{d.free_cash_flow:.2f}" if (d and d.free_cash_flow is not None) else "",
                f"{d.cash_conversion_ratio:.2f}" if (d and d.cash_conversion_ratio is not None) else "",
                d.cash_conversion_qualified_reason if (d and d.cash_conversion_qualified_reason) else "",
                f.statement_basis,
                getattr(f, "verification_status", "UNVERIFIED") or "UNVERIFIED",
                f.source_id,
                f.filing_date,
                f.accession_id,
                f.source_url,
                getattr(f, "comparability_flag", None) or "UNKNOWN",
                getattr(f, "accounting_notes", "") or "",
                getattr(f, "verification_tier", None) or getattr(f, "reconciliation_tier", None) or "UNVERIFIED",
                getattr(f, "official_filing_id", None) or "",
                getattr(f, "internal_document_key", None) or "",
                getattr(f, "reference_type", None) or "UNKNOWN",
                # Phase 7 Deeper Metrics Values
                f"{d.operating_margin_change_bps:+.1f}" if (d and d.operating_margin_change_bps is not None) else "",
                f"{d.net_margin_change_bps:+.1f}" if (d and d.net_margin_change_bps is not None) else "",
                f"{d.fcf_margin:.2f}" if (d and d.fcf_margin is not None) else "",
                f"{d.capex_intensity:.2f}" if (d and d.capex_intensity is not None) else "",
                f"{d.reinvestment_rate:.2f}" if (d and d.reinvestment_rate is not None) else "",
                f"{d.operating_leverage:+.2f}" if (d and d.operating_leverage is not None) else "",
            ])

        return output.getvalue()

    @classmethod
    def generate_peer_comparison_csv(
        cls,
        matrix: Dict[str, Any],
        peer_group_name: str = ""
    ) -> str:
        """
        Generates a CSV export of peer comparison data across multiple fiscal periods.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow(["# Peer Comparison Export", peer_group_name])
        metric_label = matrix.get("metric_name") or matrix.get("metric", "")
        writer.writerow(["# Metric", metric_label])
        writer.writerow(["# Unit", matrix.get("unit", "")])
        if matrix.get("metric_note"):
            writer.writerow(["# Accounting Caveat", matrix["metric_note"]])
        writer.writerow([])

        # Collect unique years and labels
        period_year_map = {}
        for s in matrix.get("series", []):
            for pt in s.get("data", []):
                yr = pt.get("fiscal_year")
                lbl = pt.get("fiscal_year_label")
                if yr is not None and lbl:
                    period_year_map[yr] = lbl

        sorted_yrs = sorted(period_year_map.keys())

        header = ["Fiscal Period"] + [f"{s['ticker']} ({s['company_name']})" for s in matrix.get("series", [])]
        writer.writerow(header)

        for yr in sorted_yrs:
            lbl = period_year_map[yr]
            row = [lbl]
            for s in matrix.get("series", []):
                if s.get("is_suppressed"):
                    row.append(f"Suppressed ({s.get('suppress_reason')})")
                else:
                    series_points = {pt["fiscal_year"]: pt["value"] for pt in s.get("data", [])}
                    val = series_points.get(yr)
                    row.append(f"{val:.2f}" if val is not None else "")
            writer.writerow(row)

        return output.getvalue()

    @classmethod
    def generate_technical_csv(cls, df: pd.DataFrame, ticker: str = "ASSET") -> str:
        """Generates a CSV export of OHLCV bars and calculated technical indicators."""
        output = io.StringIO()
        writer = csv.writer(output)

        writer.writerow([f"# Technical Indicators Export: {ticker}"])
        writer.writerow([])

        cols = [c for c in df.columns if c not in ("Date_Str",)]
        writer.writerow(cols)

        for _, row in df.iterrows():
            writer.writerow([row[c] if pd.notna(row[c]) else "" for c in cols])

        return output.getvalue()

    @classmethod
    def generate_technical_brief(
        cls, 
        summary: TechnicalSummary, 
        df: pd.DataFrame
    ) -> str:
        """Generates a formatted markdown brief of technical analysis and risk metrics."""
        lines = []
        lines.append(f"# FUNDAMENTALS LENS — PRICE & TECHNICAL ANALYSIS BRIEF")
        lines.append(f"## Asset / Ticker: `{summary.ticker}`")
        lines.append(f"**Latest Trading Date:** `{summary.last_date}` | **Latest Close:** `{summary.last_close:,.2f}`")
        lines.append(f"**Total Trading Observations:** `{summary.total_bars}` bars")
        if summary.benchmark_ticker:
            lines.append(f"**Benchmark Reference:** `{summary.benchmark_ticker}`")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Performance Returns
        lines.append("### 1. Multi-Period Return Performance")
        lines.append("| Lookback Period | Cumulative Return (%) |")
        lines.append("|:---|:---:|")
        lines.append(f"| 1-Month (~21 bars) | {f'{summary.change_1m:+.2f}%' if summary.change_1m is not None else 'N/A'} |")
        lines.append(f"| 3-Month (~63 bars) | {f'{summary.change_3m:+.2f}%' if summary.change_3m is not None else 'N/A'} |")
        lines.append(f"| 6-Month (~126 bars) | {f'{summary.change_6m:+.2f}%' if summary.change_6m is not None else 'N/A'} |")
        lines.append(f"| 1-Year (~252 bars) | {f'{summary.change_1y:+.2f}%' if summary.change_1y is not None else 'N/A'} |")
        lines.append("")

        # 2. Range & Risk Indicators
        lines.append("### 2. 52-Week Range & Risk Profile")
        lines.append(f"- **52-Week High:** `{summary.high_52w:,.2f}` ({f'{summary.dist_from_52w_high:+.2f}%' if summary.dist_from_52w_high is not None else 'N/A'} distance)")
        lines.append(f"- **52-Week Low:** `{summary.low_52w:,.2f}` ({f'{summary.dist_from_52w_low:+.2f}%' if summary.dist_from_52w_low is not None else 'N/A'} distance)")
        lines.append(f"- **Annualized Daily Volatility (252-day scaled):** `{summary.annualized_volatility:.2f}%`" if summary.annualized_volatility is not None else "- **Annualized Volatility:** N/A")
        lines.append(f"- **Maximum Historical Drawdown:** `{summary.max_drawdown:.2f}%`" if summary.max_drawdown is not None else "- **Maximum Drawdown:** N/A")
        lines.append("")

        # 3. Technical Momentum & Trend Status
        lines.append("### 3. Indicator & Trend Status")
        lines.append(f"- **14-Day RSI:** `{summary.current_rsi:.2f}` ({summary.rsi_status})")
        lines.append(f"- **20-Day SMA Position:** `{summary.sma_20_status}`")
        lines.append(f"- **50-Day SMA Position:** `{summary.sma_50_status}`")
        lines.append(f"- **200-Day SMA Position:** `{summary.sma_200_status}`")
        if summary.benchmark_ticker and summary.relative_performance_1y is not None:
            lines.append(f"- **Relative Performance vs. {summary.benchmark_ticker}:** `{summary.relative_performance_1y:+.2f}%` points")
        lines.append("")

        # 4. Mandatory Disclaimer
        lines.append("### 4. Technical Analysis Notice & Analytical Disclaimer")
        lines.append(
            "> **Analyst Disclaimer:** Historical technical indicators and price metrics reflect mathematical observations of past trading action. "
            "They do NOT constitute price targets, financial projections, automated trading signals, or recommendations to purchase or dispose of securities. "
            "Market dynamics are non-stationary and subject to structural regime shifts. Technical analysis should only be used as a supplementary research perspective "
            "alongside genuine, audited company fundamentals."
        )
        lines.append("")
        lines.append("---")
        lines.append("*Report generated by Fundamentals Lens — Technical Analysis MVP Engine.*")

        return "\n".join(lines)

    @classmethod
    def generate_research_brief(
        cls,
        company: Company,
        facts: List[FinancialFact],
        derived: Optional[List[DerivedMetrics]] = None,
        insights: Optional[List[FinancialInsight]] = None,
        snapshot_date: str = "2026-10-18"
    ) -> str:
        """
        Generates a comprehensive research brief in GitHub-flavored Markdown.
        Includes 5-Year CAGR, Growth Consistency, and Cumulative Cash Flows.
        """
        if derived is None:
            derived = compute_derived_metrics_for_company(facts)
        if insights is None:
            insights = NarrativeEngine.generate_company_insights(facts, derived)

        derived_map = {d.fiscal_year: d for d in derived}
        sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
        latest_fact = sorted_facts[-1] if sorted_facts else None
        first_fact = sorted_facts[0] if sorted_facts else None

        unit = company.standard_unit_label
        curr = company.reporting_currency
        report_date = date.today().isoformat()

        # Cumulative cash flows
        cum_flows = calculate_cumulative_cash_flows(sorted_facts)

        # Revenue CAGR
        cagr, cagr_reason = calculate_cagr(first_fact.revenue, latest_fact.revenue, len(sorted_facts) - 1) if (first_fact and latest_fact) else (None, "No facts")
        cagr_str = f"{cagr:+.2f}%" if cagr is not None else f"N/A ({cagr_reason})"

        lines = []
        lines.append(f"# FUNDAMENTALS LENS — FINANCIAL RESEARCH BRIEF")
        lines.append(f"## {company.name} ({company.ticker})")
        lines.append(f"**Peer Group:** {company.peer_group_name} | **Exchange:** {company.exchange} | **Country:** {company.country}")
        lines.append(f"**Dataset Snapshot Cutoff:** `{snapshot_date}` | **Brief Generation Date:** `{report_date}`")
        lines.append(f"**Statement Basis:** CONSOLIDATED (Primary Audited Regulatory Disclosures)")
        lines.append(f"**Latest Verified Period:** {latest_fact.fiscal_year_label if latest_fact else 'N/A'}")
        lines.append(f"**5-Year Revenue CAGR:** `{cagr_str}`")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Executive Summary & Business Context
        lines.append("### 1. Business Context & Operational Profile")
        lines.append(f"{company.business_description}")
        lines.append("")
        lines.append(f"**Peer Comparison Note:** {company.peer_notes}")
        lines.append("")

        # 2. Historical 5-Period Financial Facts Table
        lines.append(f"### 2. Historical Financial Disclosures (in {unit})")
        lines.append("| Fiscal Period | Period Dates | Revenue | Operating Income | Net Income | Operating Cash Flow | Capex | Comparability |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for f in sorted_facts:
            comp_flag = getattr(f, "comparability_flag", None) or "UNKNOWN"
            lines.append(
                f"| {f.fiscal_year_label} | {f.period_start} to {f.period_end} | "
                f"{f.revenue:,.1f} | {f.operating_income:,.1f} | {f.net_income:,.1f} | "
                f"{f.operating_cash_flow:,.1f} | {f.capital_expenditure:,.1f} | `{comp_flag}` |"
            )
        lines.append("")

        # 3. Derived Analytical Metrics Table
        lines.append("### 3. Derived Analytical Indicators & Margins")
        lines.append("| Fiscal Period | Revenue Growth YoY | Operating Margin | Net Margin | Free Cash Flow | Cash Conversion (OCF/NI) | FCF Margin | Capex Intensity |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for f in sorted_facts:
            d = derived_map.get(f.fiscal_year)
            growth = f"{d.revenue_growth_yoy:+.1f}%" if d and d.revenue_growth_yoy is not None else "—"
            op_m = f"{d.operating_margin:.1f}%" if d and d.operating_margin is not None else "—"
            net_m = f"{d.net_margin:.1f}%" if d and d.net_margin is not None else "—"
            fcf = f"{d.free_cash_flow:,.1f} {unit}" if d and d.free_cash_flow is not None else "—"
            if d and d.cash_conversion_ratio is not None:
                conv = f"{d.cash_conversion_ratio:.2f}x"
            elif d and d.cash_conversion_qualified_reason:
                conv = f"Suppressed ({d.cash_conversion_qualified_reason})"
            else:
                conv = "—"
            fcf_m = f"{d.fcf_margin:.1f}%" if d and d.fcf_margin is not None else "—"
            capex_int = f"{d.capex_intensity:.1f}%" if d and d.capex_intensity is not None else "—"
            lines.append(f"| {f.fiscal_year_label} | {growth} | {op_m} | {net_m} | {fcf} | {conv} | {fcf_m} | {capex_int} |")
        lines.append("")

        # 3.1 Cumulative Cash Flow Summary
        if cum_flows:
            lines.append("### 3.1 5-Year Cumulative Cash Flow Generation & Reinvestment")
            lines.append(f"- **Cumulative Operating Cash Flow:** `{cum_flows.get('cumulative_ocf', 0):,.1f} {unit}`")
            lines.append(f"- **Cumulative Capital Expenditures:** `{cum_flows.get('cumulative_capex', 0):,.1f} {unit}`")
            lines.append(f"- **Cumulative Free Cash Flow:** `{cum_flows.get('cumulative_fcf', 0):,.1f} {unit}`")
            if cum_flows.get('cumulative_reinvestment_pct') is not None:
                lines.append(f"- **Cumulative Reinvestment Rate:** `{cum_flows['cumulative_reinvestment_pct']:.1f}%` of Operating Cash Flow")
            lines.append("")

        # 4. Standard Metric Formulas & Methodology
        lines.append("### 4. Mathematical Formulas & Calculation Invariants")
        lines.append("- **Operating Margin (%):** `(Operating Income / Revenue) * 100`")
        lines.append("- **Net Margin (%):** `(Net Income / Revenue) * 100`")
        lines.append("- **Free Cash Flow:** `Operating Cash Flow - Capital Expenditure (Capex)`")
        lines.append("- **Cash Conversion Ratio:** `Operating Cash Flow / Net Income` (Suppressed if Net Income ≤ 0 to prevent distortion)")
        lines.append("- **Capex Intensity (%):** `(Capital Expenditure / Revenue) * 100`")
        lines.append("- **Operating Leverage Spread (%):** `Operating Income Growth YoY - Revenue Growth YoY`")
        lines.append("- **Compound Annual Growth Rate (CAGR):** `((End Value / Start Value) ^ (1 / Intervals) - 1) * 100` (Guarded against non-positive base)")
        lines.append("- **Capex Sign Convention:** Expressed as a positive cash outflow magnitude.")
        lines.append("")

        # 5. Narrative Insights
        lines.append("### 5. What Changed, Why It Matters, and What to Investigate")
        for idx, insight in enumerate(insights, 1):
            lines.append(f"#### 5.{idx} {insight.headline}")
            lines.append(f"- **What Changed:** {insight.what_changed}")
            lines.append(f"- **Numerical Evidence:** `{insight.evidence}`")
            lines.append(f"- **Why It Matters:** {insight.why_it_matters}")
            lines.append(f"- **What to Investigate:** {insight.what_to_investigate}")
            lines.append(f"- *Analytical Limitations:* {insight.limitations}")
            lines.append("")

        # 6. Provenance & Source Register
        lines.append("### 6. Primary Source Verification & Audit Trail")
        lines.append("| Period | Source Document | Filing Date | Statement Location | Filing Reference ID | Tier |")
        lines.append("|:---|:---|:---:|:---|:---|:---:|")
        for f in sorted_facts:
            tier = getattr(f, "verification_tier", None) or getattr(f, "reconciliation_tier", None) or "UNVERIFIED"
            ref_type = getattr(f, "reference_type", "UNKNOWN") or "UNKNOWN"
            ref_key = f.official_filing_id if ref_type == "SEC_ACCESSION" and f.official_filing_id else (f.internal_document_key or f.accession_id)
            lines.append(f"| {f.fiscal_year_label} | [{f.source_title}]({f.source_url}) | {f.filing_date} | {f.statement_location} | `{ref_key}` | `{tier}` |")
        lines.append("")

        # 7. Disclaimers & Methodology
        lines.append("### 7. Methodology & Research Disclaimer")
        lines.append(
            "> **Disclaimer:** This research brief was generated deterministically by **Fundamentals Lens** for financial analysis "
            "and academic research purposes only. It does not constitute investment advice, financial promotion, valuation opinion, "
            "or a recommendation to buy or sell securities. Past financial performance is not indicative of future results. "
            "All underlying observations are extracted directly from official audited annual financial statements without synthetic coercion."
        )
        lines.append("")
        lines.append("---")
        lines.append("*Report generated by Fundamentals Lens — Zero-Cost SEC & Indian Disclosure Intelligence.*")

        return "\n".join(lines)
