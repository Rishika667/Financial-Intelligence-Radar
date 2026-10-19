"""
Deterministic export utilities for Fundamentals Lens (Phase 8).
Generates company-specific CSV datasets, tabular peer comparison CSVs, technical analysis exports,
evidence registers, and formatted research briefs with explicit provenance and accounting comparability caveats.
"""
import io
import csv
from typing import List, Dict, Any, Optional
from datetime import date
import pandas as pd

from .models import Company, FinancialFact, DerivedMetrics, TechnicalSummary
from .metrics import (
    compute_derived_metrics_for_company,
    calculate_cumulative_cash_flows,
    calculate_cagr,
    evaluate_growth_consistency
)
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
        Preserves backwards-compatible column indices 0-32, with Phase 7/8 deeper indicators in 33-38.
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
            # Deeper Metrics
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
                f.verification_status,
                f.source_id,
                f.filing_date,
                f.accession_id,
                f.source_url,
                f.comparability_flag or "UNKNOWN",
                f.accounting_notes or "",
                f.reconciliation_tier or "UNVERIFIED",
                f.official_filing_id or "",
                f.internal_document_key or "",
                f.reference_type or "UNKNOWN",
                # Deeper Metrics
                f"{d.operating_margin_change_bps:.1f}" if (d and d.operating_margin_change_bps is not None) else "",
                f"{d.net_margin_change_bps:.1f}" if (d and d.net_margin_change_bps is not None) else "",
                f"{d.fcf_margin:.2f}" if (d and d.fcf_margin is not None) else "",
                f"{d.capex_intensity:.2f}" if (d and d.capex_intensity is not None) else "",
                f"{d.reinvestment_rate:.2f}" if (d and d.reinvestment_rate is not None) else "",
                f"{d.operating_leverage:.2f}" if (d and d.operating_leverage is not None) else "",
            ])

        return output.getvalue()

    @classmethod
    def generate_peer_csv(cls, matrix: Dict[str, Any], peer_group_name: str = "Peer Group") -> str:
        """
        Generates a rich, tabular CSV export of peer comparison data across multiple fiscal periods.
        Preserves company, ticker, fiscal period, period-end, metric, currency, source,
        verification status, comparability state, and suppression reasons.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        metric_label = matrix.get("metric_name") or matrix.get("metric", "")
        unit_label = matrix.get("unit", "")
        caveat = matrix.get("metric_note", "")

        writer.writerow(["# FUNDAMENTALS LENS — PEER COMPARISON AUDIT EXPORT"])
        writer.writerow([f"# Peer Group: {peer_group_name}"])
        writer.writerow([f"# Metric: {metric_label} ({unit_label})"])
        if caveat:
            writer.writerow([f"# Accounting & Comparability Caveat: {caveat}"])
        writer.writerow([])

        headers = [
            "Peer Group",
            "Ticker",
            "Company Name",
            "Country",
            "Currency",
            "Fiscal Year",
            "Fiscal Year Label",
            "Period End Date",
            "Metric Name",
            "Reported Value",
            "Standard Unit",
            "Comparability State",
            "Reconciliation Tier",
            "Suppression Status",
            "Suppression Reason"
        ]
        writer.writerow(headers)

        for s in matrix.get("series", []):
            ticker = s.get("ticker", "")
            cname = s.get("company_name", "")
            country = s.get("country", "")
            curr = s.get("currency", "")
            is_suppressed = s.get("is_suppressed", False)
            supp_reason = s.get("suppress_reason", "") or ""

            for pt in s.get("data", []):
                yr = pt.get("fiscal_year", "")
                lbl = pt.get("fiscal_year_label", "")
                p_end = pt.get("period_end", "")
                val = pt.get("value")
                comp_flag = pt.get("comparability", "DIRECT")
                tier = pt.get("verification_tier") or "UNVERIFIED"

                writer.writerow([
                    peer_group_name,
                    ticker,
                    cname,
                    country,
                    curr,
                    yr,
                    lbl,
                    p_end,
                    metric_label,
                    f"{val:.2f}" if (val is not None and not is_suppressed) else "",
                    unit_label,
                    comp_flag,
                    tier,
                    "SUPPRESSED" if is_suppressed else "COMPARABLE",
                    supp_reason
                ])

        return output.getvalue()

    @classmethod
    def generate_peer_comparison_csv(cls, matrix: Dict[str, Any], peer_group_name: str = "Peer Group") -> str:
        """
        Generates a CSV export of peer comparison data in matrix format across multiple fiscal periods.
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
    def generate_technical_csv(
        cls, 
        df: pd.DataFrame, 
        ticker: str = "ASSET",
        summary: Optional[TechnicalSummary] = None
    ) -> str:
        """
        Generates a CSV export of OHLCV bars and calculated technical indicators
        with comprehensive provenance metadata and simulated demo warnings where applicable.
        """
        output = io.StringIO()
        writer = csv.writer(output)

        is_sim = summary.is_simulated_demo if summary else False
        if is_sim:
            writer.writerow(["# DATA_TYPE: SIMULATED DEMO DATA — NOT ACTUAL MARKET HISTORY"])
            writer.writerow(["# WARNING: Prices and volumes are mathematically simulated via geometric Brownian motion for workflow demonstration only."])
        else:
            writer.writerow(["# DATA_TYPE: USER_SUPPLIED / RECORDED OHLCV MARKET DATA"])

        if summary:
            writer.writerow([f"# TICKER: {summary.ticker}"])
            writer.writerow([f"# CURRENCY: {summary.currency}"])
            writer.writerow([f"# PRICE_ADJUSTMENT_BASIS: {summary.price_adjustment_basis}"])
            writer.writerow([f"# DATE_RANGE: {df['Date_Str'].iloc[0] if 'Date_Str' in df.columns else df['Date'].iloc[0]} to {summary.last_date}"])
            writer.writerow([f"# OBSERVATIONS: {summary.total_bars} bars"])
            if summary.benchmark_ticker:
                writer.writerow([f"# BENCHMARK: {summary.benchmark_ticker} ({summary.common_benchmark_bars or 0} common bars)"])
        writer.writerow(["# INDICATOR_CONVENTIONS: SMA(20,50,200), Wilder's RSI(14), MACD(12,26,9), Bollinger Bands(20, 2.0 std, ddof=1), ATR(14)"])
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
        lines.append(f"**Research Platform:** Fundamentals Lens • Created by Rishika Dangayach")
        lines.append(f"## Asset / Ticker: `{summary.ticker}`")
        if summary.is_simulated_demo:
            lines.append("")
            lines.append("> ⚠️ **SIMULATED DEMO DATA — NOT ACTUAL MARKET HISTORY**: This technical brief reflects mathematically simulated prices generated via geometric Brownian motion. It does NOT represent real-world market transactions or historical pricing for any actual corporate security.")
            lines.append("")

        lines.append(f"**Latest Trading Date:** `{summary.last_date}` | **Latest Close:** `{summary.last_close:,.2f} {summary.currency}`")
        lines.append(f"**Total Trading Observations:** `{summary.total_bars}` bars")
        lines.append(f"**Price Adjustment Basis:** `{summary.price_adjustment_basis}`")
        if summary.benchmark_ticker:
            lines.append(f"**Benchmark Reference:** `{summary.benchmark_ticker}` (Common bars: `{summary.common_benchmark_bars or 0}`)")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 1. Performance Returns
        lines.append("### 1. Multi-Period Return Performance")
        lines.append("| Lookback Period | Cumulative Return (%) | Horizon Status |")
        lines.append("|:---|:---:|:---|")
        lines.append(f"| 1-Month (~21 bars) | {f'{summary.change_1m:+.2f}%' if summary.change_1m is not None else 'N/A'} | Short-term momentum |")
        lines.append(f"| 3-Month (~63 bars) | {f'{summary.change_3m:+.2f}%' if summary.change_3m is not None else 'N/A'} | Quarterly horizon |")
        lines.append(f"| 6-Month (~126 bars) | {f'{summary.change_6m:+.2f}%' if summary.change_6m is not None else 'N/A'} | Semi-annual horizon |")
        ret_1y_str = f"{summary.change_1y:+.2f}%" if summary.change_1y is not None else "N/A (< 252 bars)"
        lines.append(f"| 1-Year (252 bars) | {ret_1y_str} | Annual trading horizon |")
        lines.append("")

        # 2. Range & Risk Indicators
        range_label = "52-Week Range" if summary.is_full_52w else f"Available-History Range ({summary.total_bars} bars)"
        lines.append(f"### 2. {range_label} & Risk Profile")
        lines.append(f"- **High:** `{summary.high_52w:,.2f}` ({f'{summary.dist_from_52w_high:+.2f}%' if summary.dist_from_52w_high is not None else 'N/A'} distance)")
        lines.append(f"- **Low:** `{summary.low_52w:,.2f}` ({f'{summary.dist_from_52w_low:+.2f}%' if summary.dist_from_52w_low is not None else 'N/A'} distance)")
        lines.append(f"- **Annualized Daily Volatility (252-day scaled):** `{summary.annualized_volatility:.2f}%`" if summary.annualized_volatility is not None else "- **Annualized Volatility:** N/A")
        lines.append(f"- **Maximum Historical Drawdown:** `{summary.max_drawdown:.2f}%`" if summary.max_drawdown is not None else "- **Maximum Drawdown:** N/A")
        lines.append("")

        # 3. Technical Momentum & Trend Status
        lines.append("### 3. Indicator & Trend Status")
        lines.append(f"- **14-Day Wilder's RSI:** `{summary.current_rsi:.2f}` ({summary.rsi_status})")
        lines.append(f"- **20-Day SMA Position:** `{summary.sma_20_status}`")
        lines.append(f"- **50-Day SMA Position:** `{summary.sma_50_status}`")
        lines.append(f"- **200-Day SMA Position:** `{summary.sma_200_status}`")
        if summary.benchmark_ticker:
            if summary.relative_performance_1y is not None:
                lines.append(f"- **1-Year Relative Performance vs. {summary.benchmark_ticker}:** `{summary.relative_performance_1y:+.2f}%` points")
            elif summary.relative_performance_period is not None:
                lines.append(f"- **Common-Period Relative Performance vs. {summary.benchmark_ticker} ({summary.common_benchmark_bars} bars):** `{summary.relative_performance_period:+.2f}%` points")
        lines.append("")

        # 4. Mandatory Disclaimer
        lines.append("### 4. Technical Analysis Notice & Analytical Disclaimer")
        lines.append(
            "> **Analyst Disclaimer:** Historical technical indicators and price metrics reflect mathematical observations of past trading action. "
            "They do NOT constitute price targets, financial projections, automated trading signals, or recommendations to purchase or dispose of securities. "
            "Market dynamics are non-stationary and subject to structural regime shifts. Technical analysis should only be used as a supplementary research perspective "
            "alongside genuine, audited company fundamentals."
        )
        if summary.price_adjustment_basis in ("RAW_UNADJUSTED", "UNKNOWN"):
            lines.append("")
            lines.append("> ⚠️ **Corporate Action Caveat**: Price data adjustment basis is unconfirmed or raw. Stock splits, dividend payouts, or capital restructuring can cause sharp discontinuous price steps not reflective of economic returns.")

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
        snapshot_date: Optional[str] = None
    ) -> str:
        """
        Generates a comprehensive, evidence-first research brief in GitHub-flavored Markdown.
        Structured across 7 cohesive analytical sections:
        1. Executive Business Snapshot
        2. Revenue and Profitability Trajectory
        3. Cash Generation & Earnings Quality
        4. Capital Allocation & Reinvestment
        5. Peer Context & Comparability Nuance
        6. Risks & Unanswered Questions
        7. Evidence, Provenance & Methodology Summary
        """
        sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
        if derived is None:
            derived = compute_derived_metrics_for_company(sorted_facts)
        if insights is None:
            insights = NarrativeEngine.generate_company_insights(sorted_facts, derived)

        derived_map = {d.fiscal_year: d for d in derived}
        latest_fact = sorted_facts[-1] if sorted_facts else None
        first_fact = sorted_facts[0] if sorted_facts else None
        latest_derived = derived_map.get(latest_fact.fiscal_year) if latest_fact else None
        prior_fact = sorted_facts[-2] if len(sorted_facts) >= 2 else None
        prior_derived = derived_map.get(prior_fact.fiscal_year) if prior_fact else None

        unit = company.standard_unit_label
        curr = company.reporting_currency
        report_date = date.today().isoformat()
        if snapshot_date is None:
            try:
                from .data_loader import load_dataset_metadata
                meta = load_dataset_metadata()
                snap_date = meta.get("dataset_snapshot_date") or (latest_fact.filing_date if latest_fact else report_date)
            except Exception:
                snap_date = latest_fact.filing_date if latest_fact else report_date
        else:
            snap_date = snapshot_date

        # Cumulative cash flows
        cum_flows = calculate_cumulative_cash_flows(sorted_facts)

        # Revenue CAGR & Growth Consistency
        num_intervals = len(sorted_facts) - 1
        if first_fact and latest_fact and num_intervals > 0:
            cagr, cagr_reason = calculate_cagr(first_fact.revenue, latest_fact.revenue, num_intervals)
        else:
            cagr, cagr_reason = (None, "Insufficient intervals")
        cagr_str = f"{cagr:+.2f}%" if cagr is not None else f"N/A ({cagr_reason})"

        growth_rates = [d.revenue_growth_yoy for d in derived if d.revenue_growth_yoy is not None]
        consistency = evaluate_growth_consistency(growth_rates) if growth_rates else {"label": "N/A", "description": "Insufficient growth observations"}

        lines = []
        lines.append(f"# FUNDAMENTALS LENS — FINANCIAL RESEARCH BRIEF")
        lines.append(f"**Research Platform:** Fundamentals Lens • Created by Rishika Dangayach")
        lines.append(f"## {company.name} ({company.ticker})")
        lines.append(f"**Peer Group:** {company.peer_group_name} | **Exchange:** {company.exchange} | **Country:** {company.country}")
        lines.append(f"**Dataset Snapshot Cutoff:** `{snap_date}` | **Brief Generation Date:** `{report_date}`")
        lines.append(f"**Statement Basis:** CONSOLIDATED (Primary Audited Regulatory Disclosures)")
        lines.append(f"**Latest Verified Period:** {latest_fact.fiscal_year_label if latest_fact else 'N/A'}")
        lines.append(f"**5-Period Revenue CAGR ({num_intervals} intervals):** `{cagr_str}`")
        lines.append("")
        lines.append("---")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 1: Executive Business Snapshot
        # -------------------------------------------------------------
        lines.append("### 1. Executive Business Snapshot")
        lines.append("#### Business Context & Operational Profile")
        lines.append(f"{company.business_description}")
        lines.append("")
        if latest_fact:
            lines.append("**Operational Scale & Current Position:**")
            lines.append(f"- **Latest Audited Revenue ({latest_fact.fiscal_year_label}):** `{latest_fact.revenue:,.1f} {unit}` ({curr})")
            lines.append(f"- **Operating Income:** `{latest_fact.operating_income:,.1f} {unit}` | **Net Income:** `{latest_fact.net_income:,.1f} {unit}`")
            lines.append(f"- **Operating Cash Flow:** `{latest_fact.operating_cash_flow:,.1f} {unit}` | **Capital Expenditure:** `{latest_fact.capital_expenditure:,.1f} {unit}`")
            latest_fcf_val = latest_derived.free_cash_flow if latest_derived else (latest_fact.operating_cash_flow - latest_fact.capital_expenditure)
            lines.append(f"- **Free Cash Flow:** `{latest_fcf_val:,.1f} {unit}`")
            lines.append(f"- **Directional Trajectory:** 5-period revenue CAGR `{cagr_str}` with {consistency['label'].lower()} trajectory ({consistency['description']}).")
            lines.append(f"- **Evidence & Verification Status:** `{len(sorted_facts)} periods verified` under primary reconciliation tier `{latest_fact.reconciliation_tier or 'UNVERIFIED'}`.")
            lines.append("")

        lines.append(f"#### Historical Financial Disclosures (in {unit})")
        lines.append("| Fiscal Period | Period Dates | Revenue | Operating Income | Net Income | Operating Cash Flow | Capex | Comparability | Tier |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|")
        for f in sorted_facts:
            comp_flag = getattr(f, "comparability_flag", None) or "UNKNOWN"
            tier = getattr(f, "reconciliation_tier", None) or "UNVERIFIED"
            lines.append(
                f"| {f.fiscal_year_label} | {f.period_start} to {f.period_end} | "
                f"{f.revenue:,.1f} | {f.operating_income:,.1f} | {f.net_income:,.1f} | "
                f"{f.operating_cash_flow:,.1f} | {f.capital_expenditure:,.1f} | `{comp_flag}` | `{tier}` |"
            )
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 2: Revenue and Profitability Trajectory
        # -------------------------------------------------------------
        lines.append("### 2. Revenue and Profitability Trajectory")
        lines.append("#### Derived Analytical Indicators & Margins")
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

        # Trajectory details with exact expansion/deterioration periods
        lines.append("#### Trajectory Analysis & Margin Dynamics")
        op_margins = [(d.fiscal_year_label, d.operating_margin) for d in derived if d.operating_margin is not None]
        net_margins = [(d.fiscal_year_label, d.net_margin) for d in derived if d.net_margin is not None]
        if op_margins:
            peak_op = max(op_margins, key=lambda x: x[1])
            trough_op = min(op_margins, key=lambda x: x[1])
            lines.append(f"- **Operating Margin Range:** Traversed from trough of `{trough_op[1]:.2f}%` ({trough_op[0]}) to peak of `{peak_op[1]:.2f}%` ({peak_op[0]}).")
        if net_margins:
            peak_net = max(net_margins, key=lambda x: x[1])
            trough_net = min(net_margins, key=lambda x: x[1])
            lines.append(f"- **Net Margin Range:** Traversed from trough of `{trough_net[1]:.2f}%` ({trough_net[0]}) to peak of `{peak_net[1]:.2f}%` ({peak_net[0]}).")

        # Period-by-period expansion / deterioration
        if len(derived) >= 2:
            lines.append("- **Period-by-Period Margin Movement:**")
            for i in range(1, len(derived)):
                p_prev = derived[i-1]
                p_curr = derived[i]
                if p_curr.operating_margin is not None and p_prev.operating_margin is not None:
                    delta_pts = p_curr.operating_margin - p_prev.operating_margin
                    bps = delta_pts * 100.0
                    status = "Expanded" if delta_pts > 0 else "Compressed" if delta_pts < 0 else "Unchanged"
                    rev_g = f"{p_curr.revenue_growth_yoy:+.1f}%" if p_curr.revenue_growth_yoy is not None else "N/A"
                    lines.append(f"  - `{p_prev.fiscal_year_label} -> {p_curr.fiscal_year_label}`: Operating margin {status.lower()} by `{delta_pts:+.2f} pts` (`{bps:+.0f} bps`) to `{p_curr.operating_margin:.2f}%` (Revenue growth: `{rev_g}`).")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 3: Cash Generation & Earnings Quality
        # -------------------------------------------------------------
        lines.append("### 3. Cash Generation & Earnings Quality")
        lines.append("#### Cash Flow Generation & Input Reconciliation")
        lines.append("| Fiscal Period | Operating Cash Flow | Capex | Free Cash Flow | Net Income | Cash Conversion (OCF/NI) | Conversion Status |")
        lines.append("|:---|:---:|:---:|:---:|:---:|:---:|:---|")
        for f in sorted_facts:
            d = derived_map.get(f.fiscal_year)
            fcf_val = f"{d.free_cash_flow:,.1f} {unit}" if d and d.free_cash_flow is not None else "—"
            if d and d.cash_conversion_ratio is not None:
                conv_val = f"{d.cash_conversion_ratio:.2f}x"
                conv_stat = "High Conversion (≥ 1.0x)" if d.cash_conversion_ratio >= 1.0 else "Sub-Net Income (< 1.0x)"
            elif d and d.cash_conversion_qualified_reason:
                conv_val = "Suppressed"
                conv_stat = f"Suppressed: {d.cash_conversion_qualified_reason}"
            else:
                conv_val = "—"
                conv_stat = "N/A"
            lines.append(f"| {f.fiscal_year_label} | {f.operating_cash_flow:,.1f} | {f.capital_expenditure:,.1f} | {fcf_val} | {f.net_income:,.1f} | {conv_val} | {conv_stat} |")
        lines.append("")

        lines.append("#### Cash vs. Earnings Divergence Analysis")
        lines.append("- **Valuation & Accounting Invariants:**")
        lines.append("  - `Free Cash Flow = Operating Cash Flow - Capital Expenditure`")
        lines.append("  - `Cash Conversion Ratio = Operating Cash Flow / Net Income`")
        if len(sorted_facts) >= 2:
            lines.append("- **Accrual vs. Cash Divergence Observations:**")
            for i in range(1, len(sorted_facts)):
                f_prev = sorted_facts[i-1]
                f_curr = sorted_facts[i]
                ni_chg = f_curr.net_income - f_prev.net_income
                ocf_chg = f_curr.operating_cash_flow - f_prev.operating_cash_flow
                if ni_chg > 0 and ocf_chg < 0:
                    lines.append(f"  - `⚠️ {f_prev.fiscal_year_label} -> {f_curr.fiscal_year_label}`: **Accrual Divergence Detected**: Net income expanded by `{ni_chg:+,.1f} {unit}`, while Operating Cash Flow declined by `{abs(ocf_chg):,.1f} {unit}`. Indicates cash collection lagged accounting earnings.")
                elif ni_chg < 0 and ocf_chg > 0:
                    lines.append(f"  - `ℹ️ {f_prev.fiscal_year_label} -> {f_curr.fiscal_year_label}`: **Counter-Cyclical Cash Resilience**: Net income declined by `{abs(ni_chg):,.1f} {unit}`, but Operating Cash Flow expanded by `{ocf_chg:+,.1f} {unit}`.")
                else:
                    lines.append(f"  - `✅ {f_prev.fiscal_year_label} -> {f_curr.fiscal_year_label}`: Directional alignment between Net Income ({ni_chg:+,.1f} {unit}) and OCF ({ocf_chg:+,.1f} {unit}).")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 4: Capital Allocation & Reinvestment
        # -------------------------------------------------------------
        lines.append("### 4. Capital Allocation & Reinvestment")
        if cum_flows and not cum_flows.get("suppressed"):
            comp_badge = "Complete 5-Period Aggregate" if cum_flows.get("is_complete") else f"Partial Aggregate ({cum_flows.get('periods_included')}/{cum_flows.get('total_periods')} periods)"
            lines.append(f"#### 4.1 Cumulative Cash Flow Generation ({comp_badge})")
            lines.append(f"- **Cumulative Operating Cash Flow:** `{cum_flows.get('cumulative_ocf', 0):,.1f} {unit}`")
            lines.append(f"- **Cumulative Capital Expenditures:** `{cum_flows.get('cumulative_capex', 0):,.1f} {unit}`")
            lines.append(f"- **Cumulative Free Cash Flow:** `{cum_flows.get('cumulative_fcf', 0):,.1f} {unit}`")
            if cum_flows.get('cumulative_reinvestment_pct') is not None:
                lines.append(f"- **Cumulative Reinvestment Rate:** `{cum_flows['cumulative_reinvestment_pct']:.1f}%` of Operating Cash Flow")
            lines.append("")
        elif cum_flows and cum_flows.get("suppressed"):
            lines.append("#### 4.1 Cumulative Cash Flow Generation")
            lines.append(f"- *Cumulative metrics suppressed:* {cum_flows.get('suppress_reason')}")
            lines.append("")

        lines.append("#### 4.2 Reinvestment Dynamics & Productive Capex")
        if first_fact and latest_fact and latest_derived:
            first_der = derived_map.get(first_fact.fiscal_year)
            first_capex_int = f"{first_der.capex_intensity:.1f}%" if first_der and first_der.capex_intensity is not None else "N/A"
            latest_capex_int = f"{latest_derived.capex_intensity:.1f}%" if latest_derived and latest_derived.capex_intensity is not None else "N/A"
            lines.append(f"- **Capital Intensity Shift:** Capex intensity transitioned from `{first_capex_int}` ({first_fact.fiscal_year_label}) to `{latest_capex_int}` ({latest_fact.fiscal_year_label}).")
            if prior_fact and prior_derived and prior_fact.capital_expenditure > 0:
                capex_diff = latest_fact.capital_expenditure - prior_fact.capital_expenditure
                if capex_diff < -0.10 * prior_fact.capital_expenditure and latest_derived.free_cash_flow and latest_derived.free_cash_flow > 0:
                    lines.append(f"- **Capital Harvesting Indicator:** Capex declined by `{abs(capex_diff):,.1f} {unit}` in {latest_fact.fiscal_year_label}. Strong FCF generation reflects capital expenditure moderation rather than pure operational acceleration.")
                else:
                    lines.append(f"- **Productive Reinvestment:** Capital reinvestment maintained consistent operational scale supporting property, plant, and equipment requirements.")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 5: Peer Context & Comparability Nuance
        # -------------------------------------------------------------
        lines.append("### 5. Peer Context & Comparability Nuance")
        lines.append(f"**Peer Group Benchmark:** `{company.peer_group_name}` (`{company.peer_group_id}`)")
        lines.append(f"**Peer Comparison Note:** {company.peer_notes}")
        lines.append("")
        lines.append("**Comparability & Normalization Safeguards:**")
        lines.append(f"- **Currency Framework:** Primary reporting currency is `{curr}` ({unit}). Nominal sums are strictly incomparable across cross-currency peers without FX translation. Percentage margins and YoY growth rates should be prioritized for cross-border benchmarking.")
        lines.append(f"- **Fiscal Calendar Alignment:** Company fiscal year ends in `{latest_fact.period_end[5:7] if latest_fact else 'annual cycle'}`. In peer comparisons, periods correspond to the nearest matching annual reporting cycle.")
        is_proxy = any(getattr(f, "comparability_flag", "") == "PROXY" or "Proxy" in (f.accounting_notes or "") for f in sorted_facts)
        if is_proxy:
            lines.append("- **Proxy Metric Suppression Active:** Operating profit utilizes a non-standard or proxy definition (e.g. PBEI or EBITDA). In Fundamentals Lens peer comparison views, unadjusted direct ranking and chart series are suppressed against standard EBIT peers to maintain analyst integrity.")
        else:
            lines.append("- **Direct Comparability Standard:** Operating income follows primary GAAP/Ind AS operating profit conventions.")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 6: Risks & Unanswered Questions
        # -------------------------------------------------------------
        lines.append("### 6. Risks & Unanswered Questions")
        lines.append("The following analytical risks and follow-up questions are derived strictly from verified financial facts without speculative macroeconomic extrapolation:")
        risk_count = 0
        if latest_derived and prior_derived and latest_derived.operating_margin is not None and prior_derived.operating_margin is not None:
            margin_drop = prior_derived.operating_margin - latest_derived.operating_margin
            if margin_drop >= 1.0:
                risk_count += 1
                lines.append(f"- **Operating Margin Compression:** Operating margin compressed by `{margin_drop:.2f} percentage points` (`{margin_drop*100.0:.0f} bps`) in {latest_fact.fiscal_year_label}. *Question to investigate:* Did input costs increase or did competitive pricing pressure dilute gross margins?")
        if latest_derived and latest_derived.cash_conversion_ratio is not None and latest_derived.cash_conversion_ratio < 0.80:
            risk_count += 1
            lines.append(f"- **Sub-Par Cash Conversion:** Operating cash conversion stood at `{latest_derived.cash_conversion_ratio:.2f}x` in {latest_fact.fiscal_year_label} (below 1.0x threshold). *Question to investigate:* Examine the statement of cash flows for trade receivables buildup or inventory accumulation.")
        elif latest_derived and latest_derived.cash_conversion_qualified_reason:
            risk_count += 1
            lines.append(f"- **Suppressed Conversion Ratio:** Cash conversion was suppressed because Net Income was non-positive or near zero (`{latest_derived.cash_conversion_qualified_reason}`). *Question to investigate:* Analyze operating cash flow directly independent of accounting net loss.")
        if first_fact and (first_fact.revenue is None or first_fact.revenue <= 0):
            risk_count += 1
            lines.append(f"- **Non-Positive Growth Baseline:** Base period revenue was non-positive, preventing CAGR calculation. *Question to investigate:* Verify whether business restructuring occurred in early periods.")
        if len(sorted_facts) < 5:
            risk_count += 1
            lines.append(f"- **Truncated Historical Horizon:** Available dataset contains `{len(sorted_facts)}` periods instead of the full 5-year standard. Multi-year cyclical patterns may not be fully captured.")
        if is_proxy:
            risk_count += 1
            lines.append(f"- **Accounting Definition Limitations:** Operating profit utilizes a proxy definition. Direct comparison against peers using standard operating profit requires manual adjustments.")
        if risk_count == 0:
            lines.append("- **Stable Fundamental Parameters:** No severe multi-year margin collapses (>100 bps) or acute cash conversion deficits were detected across the verified historical facts. Analysts should investigate ongoing segment disclosures and competitive positioning.")
        lines.append("")

        # -------------------------------------------------------------
        # SECTION 7: Evidence, Provenance & Methodology Summary
        # -------------------------------------------------------------
        lines.append("### 7. Evidence, Provenance & Methodology Summary")
        lines.append("#### 7.1 Mathematical Formulas & Calculation Invariants")
        lines.append("- **Operating Margin (%):** `(Operating Income / Revenue) * 100`")
        lines.append("- **Net Margin (%):** `(Net Income / Revenue) * 100`")
        lines.append("- **Free Cash Flow:** `Operating Cash Flow - Capital Expenditure (Capex)`")
        lines.append("- **Cash Conversion Ratio:** `Operating Cash Flow / Net Income` (Suppressed if Net Income ≤ 0 to prevent distortion)")
        lines.append("- **Capex Intensity (%):** `(Capital Expenditure / Revenue) * 100`")
        lines.append("- **Operating Leverage Spread (%):** `Operating Income Growth YoY - Revenue Growth YoY`")
        lines.append("- **Compound Annual Growth Rate (CAGR):** `((End Value / Start Value) ^ (1 / Intervals) - 1) * 100` (Guarded against non-positive base)")
        lines.append("- **Capex Sign Convention:** Expressed as a positive cash outflow magnitude.")
        lines.append("")

        lines.append("#### 7.2 Primary Source Verification & Audit Trail")
        lines.append("| Period | Source Document | Filing Date | Statement Location | Filing Reference ID | Tier |")
        lines.append("|:---|:---|:---:|:---|:---|:---:|")
        for f in sorted_facts:
            tier = getattr(f, "reconciliation_tier", None) or "UNVERIFIED"
            ref_type = getattr(f, "reference_type", "UNKNOWN") or "UNKNOWN"
            ref_key = f.official_filing_id if ref_type == "SEC_ACCESSION" and f.official_filing_id else (f.internal_document_key or f.accession_id)
            lines.append(f"| {f.fiscal_year_label} | [{f.source_title}]({f.source_url}) | {f.filing_date} | {f.statement_location} | `{ref_key}` | `{tier}` |")
        lines.append("")

        lines.append("#### 7.3 Methodology & Research Disclaimer")
        lines.append(
            "> **Disclaimer:** This research brief was generated deterministically by **Fundamentals Lens** for financial analysis "
            "and academic research purposes only. It does not constitute investment advice, financial promotion, valuation opinion, "
            "or a recommendation to buy or sell securities. Past financial performance is not indicative of future results. "
            "All underlying observations are extracted directly from official audited annual financial statements without synthetic coercion."
        )
        lines.append("")

        # -------------------------------------------------------------
        # Granular Narrative Insights
        # -------------------------------------------------------------
        lines.append("### What Changed, Why It Matters, and What to Investigate")
        for idx, insight in enumerate(insights, 1):
            lines.append(f"#### Insight {idx}: {insight.headline}")
            lines.append(f"- **What Changed:** {insight.what_changed}")
            lines.append(f"- **Numerical Evidence:** `{insight.evidence}`")
            lines.append(f"- **Why It Matters:** {insight.why_it_matters}")
            lines.append(f"- **What to Investigate:** {insight.what_to_investigate}")
            lines.append(f"- *Analytical Limitations:* {insight.limitations}")
            lines.append("")

        lines.append("---")
        lines.append("*Report generated by Fundamentals Lens — Zero-Cost SEC & Indian Disclosure Intelligence.*")

        return "\n".join(lines)

    @classmethod
    def generate_evidence_summary_csv(cls, evidence_records: List[Dict[str, Any]]) -> str:
        """Generates a downloadable CSV of all metric-level evidence records and reconciliation tiers."""
        output = io.StringIO()
        writer = csv.writer(output)

        headers = [
            "Ticker",
            "Company Name",
            "Fiscal Year",
            "Fiscal Year Label",
            "Period End",
            "Statement Basis",
            "Metric Key",
            "Statement Name",
            "Statement Locator",
            "Reported Line Item",
            "Reported Value",
            "Canonical Value",
            "Unit",
            "Reconciliation Tier",
            "Comparison Result",
            "Discrepancy Note",
            "Reference Type",
            "Official Filing ID",
            "Internal Document Key"
        ]
        writer.writerow(headers)

        primary_metrics = ["revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"]

        for rec in evidence_records:
            t = rec.get("ticker", "")
            cname = rec.get("company_name", "")
            fy = rec.get("fiscal_year", "")
            fylbl = rec.get("fiscal_year_label", "")
            pend = rec.get("period_end", "")
            basis = rec.get("statement_basis", "CONSOLIDATED")
            ref_type = rec.get("reference_type", "")
            off_id = rec.get("official_filing_id", "") or ""
            int_key = rec.get("internal_document_key", "") or ""
            unit = rec.get("unit", "")

            metrics = rec.get("metrics", {})
            for m in primary_metrics:
                m_ev = metrics.get(m, {})
                rep_val = m_ev.get("reported_value")
                canon_val = m_ev.get("canonical_value")

                writer.writerow([
                    t,
                    cname,
                    fy,
                    fylbl,
                    pend,
                    basis,
                    m,
                    m_ev.get("statement_name", ""),
                    m_ev.get("statement_locator", ""),
                    m_ev.get("reported_line_item", ""),
                    str(rep_val) if rep_val is not None else "",
                    str(canon_val) if canon_val is not None else "",
                    unit,
                    m_ev.get("reconciliation_tier", ""),
                    m_ev.get("comparison_result", ""),
                    m_ev.get("discrepancy_note", ""),
                    ref_type,
                    off_id,
                    int_key
                ])

        return output.getvalue()
