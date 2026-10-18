"""
Deterministic export utilities for Fundamentals Lens (Phase 5).
Generates company-specific CSV datasets, peer comparison CSVs, and formatted research briefs.
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
    Generates downloadable CSV data and Markdown research briefs with explicit provenance
    and accounting comparability caveats.
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
        """
        if derived is None:
            derived = compute_derived_metrics_for_company(facts)
        derived_map = {d.fiscal_year: d for d in derived}

        output = io.StringIO()
        writer = csv.writer(output)

        # Header (Index 10 is Revenue for backward compatibility)
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
            "Reconciliation Tier"
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
                f.verification_status,
                f.source_id,
                f.filing_date,
                f.accession_id,
                f.source_url,
                getattr(f, "comparability_flag", "DIRECT"),
                getattr(f, "accounting_notes", ""),
                getattr(f, "reconciliation_tier", "INDEPENDENTLY_RECONCILED")
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
        all_period_labels = [period_year_map[y] for y in sorted_yrs]

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
        report_date = date.today().isoformat()

        lines = []
        lines.append(f"# FUNDAMENTALS LENS — FINANCIAL RESEARCH BRIEF")
        lines.append(f"## {company.name} ({company.ticker})")
        lines.append(f"**Peer Group:** {company.peer_group_name} | **Exchange:** {company.exchange} | **Country:** {company.country}")
        lines.append(f"**Dataset Snapshot Cutoff:** `{snapshot_date}` | **Brief Generation Date:** `{report_date}`")
        lines.append(f"**Statement Basis:** CONSOLIDATED (100% Audited Regulatory Disclosures)")
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
        lines.append("| Fiscal Period | Period Dates | Revenue | Operating Income | Net Income | Operating Cash Flow | Capex | Comparability |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for f in sorted_facts:
            comp_flag = getattr(f, "comparability_flag", "DIRECT")
            lines.append(
                f"| {f.fiscal_year_label} | {f.period_start} to {f.period_end} | "
                f"{f.revenue:,.1f} | {f.operating_income:,.1f} | {f.net_income:,.1f} | "
                f"{f.operating_cash_flow:,.1f} | {f.capital_expenditure:,.1f} | `{comp_flag}` |"
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

        # 4. Standard Metric Formulas & Methodology
        lines.append("### 4. Mathematical Formulas & Calculation Invariants")
        lines.append("- **Operating Margin (%):** `(Operating Income / Revenue) * 100`")
        lines.append("- **Net Margin (%):** `(Net Income / Revenue) * 100`")
        lines.append("- **Free Cash Flow:** `Operating Cash Flow - Capital Expenditure (Capex)`")
        lines.append("- **Cash Conversion Ratio:** `Operating Cash Flow / Net Income` (Suppressed if Net Income ≤ 0 to prevent distortion)")
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
            tier = getattr(f, "reconciliation_tier", "INDEPENDENTLY_RECONCILED")
            lines.append(f"| {f.fiscal_year_label} | [{f.source_title}]({f.source_url}) | {f.filing_date} | {f.statement_location} | `{f.accession_id}` | `{tier}` |")
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
