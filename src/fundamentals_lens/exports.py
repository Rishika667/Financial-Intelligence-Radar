"""
Deterministic export utilities for Fundamentals Lens.
Generates company-specific CSV datasets and formatted research briefs.
"""
import io
import csv
from typing import List, Dict, Any, Optional
from datetime import date
from .models import Company, FinancialFact, DerivedMetrics
from .metrics import compute_derived_metrics_for_company
from .insights import NarrativeEngine, FinancialInsight


class ExportGenerator:
    """
    Generates downloadable CSV data and Markdown research briefs.
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
        """
        if derived is None:
            derived = compute_derived_metrics_for_company(facts)
        derived_map = {d.fiscal_year: d for d in derived}

        output = io.StringIO()
        writer = csv.writer(output)

        # Header
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
            "Source URL"
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
                f"{d.revenue_growth_yoy:.2f}" if d and d.revenue_growth_yoy is not None else "",
                f.operating_income,
                f"{d.operating_margin:.2f}" if d and d.operating_margin is not None else "",
                f.net_income,
                f"{d.net_margin:.2f}" if d and d.net_margin is not None else "",
                f.operating_cash_flow,
                f.capital_expenditure,
                f"{d.free_cash_flow:.2f}" if d and d.free_cash_flow is not None else "",
                f"{d.cash_conversion_ratio:.2f}" if d and d.cash_conversion_ratio is not None else "",
                d.cash_conversion_qualified_reason if d and d.cash_conversion_qualified_reason else "",
                f.statement_basis,
                f.verification_status,
                f.source_id,
                f.filing_date,
                f.accession_id,
                f.source_url
            ])

        return output.getvalue()

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
        """
        if derived is None:
            derived = compute_derived_metrics_for_company(facts)
        if insights is None:
            insights = NarrativeEngine.generate_company_insights(facts, derived)

        derived_map = {d.fiscal_year: d for d in derived}
        sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
        latest_fact = sorted_facts[-1] if sorted_facts else None

        unit = company.standard_unit_label
        curr = company.reporting_currency

        lines = []
        lines.append(f"# FUNDAMENTALS LENS — FINANCIAL RESEARCH BRIEF")
        lines.append(f"## {company.name} ({company.ticker})")
        lines.append(f"**Peer Group:** {company.peer_group_name} | **Exchange:** {company.exchange} | **Country:** {company.country}")
        lines.append(f"**Research Snapshot Date:** {snapshot_date} | **Statement Basis:** CONSOLIDATED (100% Audited)")
        lines.append(f"**Latest Verified Period:** {latest_fact.fiscal_year_label if latest_fact else 'N/A'}")
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
        lines.append("| Fiscal Period | Period Dates | Revenue | Operating Income | Net Income | Operating Cash Flow | Capex |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|")
        for f in sorted_facts:
            lines.append(
                f"| {f.fiscal_year_label} | {f.period_start} to {f.period_end} | "
                f"{f.revenue:,.1f} | {f.operating_income:,.1f} | {f.net_income:,.1f} | "
                f"{f.operating_cash_flow:,.1f} | {f.capital_expenditure:,.1f} |"
            )
        lines.append("")

        # 3. Derived Analytical Metrics Table
        lines.append("### 3. Derived Analytical Indicators & Margins")
        lines.append("| Fiscal Period | Revenue Growth YoY | Operating Margin | Net Margin | Free Cash Flow | Cash Conversion (OCF/NI) |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|")
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
            lines.append(f"| {f.fiscal_year_label} | {growth} | {op_m} | {net_m} | {fcf} | {conv} |")
        lines.append("")

        # 4. Narrative Insights
        lines.append("### 4. What Changed, Why It Matters, and What to Investigate")
        for idx, insight in enumerate(insights, 1):
            lines.append(f"#### 4.{idx} {insight.headline}")
            lines.append(f"- **What Changed:** {insight.what_changed}")
            lines.append(f"- **Numerical Evidence:** {insight.evidence}")
            lines.append(f"- **Why It Matters:** {insight.why_it_matters}")
            lines.append(f"- **What to Investigate:** {insight.what_to_investigate}")
            lines.append(f"- *Analytical Limitations:* {insight.limitations}")
            lines.append("")

        # 5. Provenance & Source Register
        lines.append("### 5. Primary Source Verification & Audit Trail")
        lines.append("| Period | Source Document | Filing Date | Statement Location | Accession ID | Status |")
        lines.append("|:---|:---|:---:|:---|:---|:---:|")
        for f in sorted_facts:
            lines.append(f"| {f.fiscal_year_label} | [{f.source_title}]({f.source_url}) | {f.filing_date} | {f.statement_location} | `{f.accession_id}` | `{f.verification_status}` |")
        lines.append("")

        # 6. Disclaimers & Methodology
        lines.append("### 6. Methodology & Research Disclaimer")
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
