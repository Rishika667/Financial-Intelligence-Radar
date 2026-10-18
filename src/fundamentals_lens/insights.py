"""
Rule-based analytical narrative engine for Fundamentals Lens.
Generates deterministic, evidence-linked insights:
'What changed, why it matters, and what to investigate'
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from .models import FinancialFact, DerivedMetrics
from .metrics import (
    compute_derived_metrics_for_company,
    calculate_cagr,
    evaluate_growth_consistency,
    calculate_cumulative_cash_flows,
    calculate_margin_volatility
)


@dataclass
class FinancialInsight:
    category: str
    headline: str
    what_changed: str
    evidence: str
    why_it_matters: str
    what_to_investigate: str
    limitations: str


class NarrativeEngine:
    """
    Deterministic rule-based narrative generator.
    Translates verified financial facts and derived metrics into actionable analyst commentary.
    """

    @classmethod
    def generate_company_insights(
        cls, 
        facts: List[FinancialFact],
        derived: Optional[List[DerivedMetrics]] = None
    ) -> List[FinancialInsight]:
        if not facts or len(facts) < 2:
            return [
                FinancialInsight(
                    category="DATA_LIMITATION",
                    headline="Insufficient Historical Periods for Trend Analysis",
                    what_changed="Fewer than two consecutive annual reporting periods are available.",
                    evidence=f"Available periods: {[f.fiscal_year_label for f in facts]}",
                    why_it_matters="Multi-year trend direction cannot be reliably determined from fewer than two periods.",
                    what_to_investigate="Verify whether prior annual reports or regulatory filings can be retrieved.",
                    limitations="Trend analysis requires at least two consecutive periods."
                )
            ]

        # Defensive sorting: ensure facts are in chronological order regardless of caller list order
        sorted_facts = sorted(facts, key=lambda f: f.fiscal_year)

        # Align or compute derived metrics in matching chronological order
        if derived is None:
            sorted_derived = compute_derived_metrics_for_company(sorted_facts)
        else:
            derived_map = {d.fiscal_year: d for d in derived}
            sorted_derived = [derived_map[f.fiscal_year] for f in sorted_facts if f.fiscal_year in derived_map]
            if len(sorted_derived) != len(sorted_facts):
                sorted_derived = compute_derived_metrics_for_company(sorted_facts)

        insights: List[FinancialInsight] = []

        # 1. Revenue Trajectory Insight
        rev_insight = cls._analyze_revenue_trajectory(sorted_facts, sorted_derived)
        if rev_insight:
            insights.append(rev_insight)

        # 2. Operating Margin & Profitability Insight
        margin_insight = cls._analyze_margin_trajectory(sorted_facts, sorted_derived)
        if margin_insight:
            insights.append(margin_insight)

        # 3. Cash Flow Generation & Free Cash Flow Insight
        cash_insight = cls._analyze_cash_flow(sorted_facts, sorted_derived)
        if cash_insight:
            insights.append(cash_insight)

        # 4. Earnings Quality & Cash Conversion Insight
        conv_insight = cls._analyze_cash_conversion(sorted_facts, sorted_derived)
        if conv_insight:
            insights.append(conv_insight)

        # 5. Capital Intensity & Reinvestment
        capex_insight = cls._analyze_capital_reinvestment(sorted_facts, sorted_derived)
        if capex_insight:
            insights.append(capex_insight)

        return insights

    @staticmethod
    def _analyze_revenue_trajectory(
        facts: List[FinancialFact], 
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        latest_fact = facts[-1]
        first_fact = facts[0]
        latest_derived = derived[-1]
        prior_derived = derived[-2] if len(derived) >= 2 else None

        unit = latest_fact.unit
        first_rev = first_fact.revenue
        latest_rev = latest_fact.revenue
        
        # Guard against zero, negative or missing base revenue
        if first_rev is not None and first_rev > 0:
            total_growth_pct = round(((latest_rev - first_rev) / first_rev) * 100.0, 1)
            total_growth_str = f"{total_growth_pct:+.1f}%"
        else:
            total_growth_pct = None
            total_growth_str = "N/A (Non-positive baseline)"

        latest_growth = latest_derived.revenue_growth_yoy
        prior_growth = prior_derived.revenue_growth_yoy if prior_derived else None
        growth_str = f"{latest_growth:+.1f}%" if latest_growth is not None else "N/A"

        if latest_growth is None:
            headline = f"Revenue Disclosed at {latest_rev:,.0f} {unit}"
            what_changed = f"Consolidated revenue stood at {latest_rev:,.0f} {unit} in {latest_fact.fiscal_year_label}."
            why_it_matters = "Initial reporting period provides the baseline for future period comparisons."
            what_to_investigate = "Monitor subsequent audited annual disclosures to evaluate multi-year direction."
        elif latest_growth > 15.0:
            headline = f"Strong Revenue Expansion ({latest_growth:+.1f}% YoY)"
            what_changed = f"Revenue grew by {latest_growth:+.1f}% in {latest_fact.fiscal_year_label}, expanding from {first_rev:,.0f} {unit} in {first_fact.fiscal_year_label} to {latest_rev:,.0f} {unit} in {latest_fact.fiscal_year_label}."
            why_it_matters = "Double-digit top-line growth indicates significant business volume expansion, though underlying drivers (organic demand, pricing actions, consolidation, or currency movements) may warrant investigation."
            what_to_investigate = "Determine the balance between organic volume expansion, price realization, foreign exchange effects, and inorganic acquisition contributions."
        elif latest_growth < 0.0:
            headline = f"Revenue Contraction Detected ({abs(latest_growth):.1f}% YoY)"
            what_changed = f"Top-line revenue contracted by {abs(latest_growth):.1f}% in {latest_fact.fiscal_year_label} to {latest_rev:,.0f} {unit}."
            why_it_matters = "Top-line contraction can pressure operating leverage and reduce absorption of fixed overheads, warranting detailed inspection of segment demand."
            what_to_investigate = "Check product line segment disclosures, foreign currency translation impacts, and industry cyclicality factors."
        else:
            headline = f"Moderate Top-Line Trajectory ({growth_str} YoY)"
            what_changed = f"Revenue shifted by {growth_str} in {latest_fact.fiscal_year_label}, reflecting a {total_growth_str} 5-year cumulative change."
            why_it_matters = "Single-digit top-line changes may reflect mature operational scale or market conditions; however, underlying volume versus pricing trends cannot be established from consolidated top-line figures alone and warrant segment investigation."
            what_to_investigate = "Examine geographic and product-mix variations that may diverge from the consolidated growth rate."

        # Multi-year revenue CAGR and consistency analysis
        num_intervals = len(facts) - 1
        cagr, cagr_reason = calculate_cagr(first_rev, latest_rev, num_intervals)
        cagr_str = f"{cagr:+.1f}%" if cagr is not None else f"N/A ({cagr_reason})"
        growth_rates = [d.revenue_growth_yoy for d in derived[1:]]
        consistency = evaluate_growth_consistency(growth_rates)

        evidence = (
            f"5-Year Revenue: {first_rev:,.0f} {unit} ({first_fact.fiscal_year_label}) -> "
            f"{latest_rev:,.0f} {unit} ({latest_fact.fiscal_year_label}) [{total_growth_str} overall, CAGR: {cagr_str}]. "
            f"Latest YoY Growth: {growth_str} | Trajectory Consistency: {consistency['label']} ({consistency['description']})."
        )

        limitations = "Historical revenue figures reflect consolidated GAAP/Ind AS accounting and exclude subsequent forward guidance."

        return FinancialInsight(
            category="TOP_LINE_GROWTH",
            headline=headline,
            what_changed=what_changed,
            evidence=evidence,
            why_it_matters=why_it_matters,
            what_to_investigate=what_to_investigate,
            limitations=limitations
        )

    @staticmethod
    def _analyze_margin_trajectory(
        facts: List[FinancialFact], 
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        latest_fact = facts[-1]
        latest_der = derived[-1]
        prior_der = derived[-2] if len(derived) >= 2 else None

        if latest_der.operating_margin is None:
            return None

        curr_op_margin = latest_der.operating_margin
        prior_op_margin = prior_der.operating_margin if prior_der else None

        if prior_op_margin is not None:
            margin_delta = round(curr_op_margin - prior_op_margin, 2)
            if margin_delta >= 1.0:
                headline = f"Operating Margin Expansion (+{margin_delta:.2f} percentage points)"
                what_changed = f"Operating margin improved from {prior_op_margin:.1f}% in {prior_der.fiscal_year_label} to {curr_op_margin:.1f}% in {latest_der.fiscal_year_label}."
                why_it_matters = "Margin expansion may suggest operating leverage, lower input costs, favorable pricing, or product mix shifts, but specific cost causes cannot be confirmed without line-item decomposition."
                what_to_investigate = "Investigate whether gross margins expanded or whether operating expenses (SG&A/R&D) grew at a slower rate than revenue."
            elif margin_delta <= -1.0:
                headline = f"Operating Margin Compression ({margin_delta:.2f} percentage points)"
                what_changed = f"Operating margin declined from {prior_op_margin:.1f}% in {prior_der.fiscal_year_label} to {curr_op_margin:.1f}% in {latest_der.fiscal_year_label}."
                why_it_matters = "Margin compression may indicate increased production costs, competitive pricing pressure, or planned overhead investments ahead of revenue."
                what_to_investigate = "Check gross margin vs. SG&A breakdown in the notes to the financial statements to isolate the cost driver."
            else:
                headline = f"Stable Operating Profitability ({curr_op_margin:.1f}% margin)"
                what_changed = f"Operating margin held steady at {curr_op_margin:.1f}% (change of {margin_delta:+.2f} percentage points YoY)."
                why_it_matters = "Predictable operating margins suggest consistent operational execution; however, underlying gross margins and overhead dynamics may warrant investigation to confirm sustainable cost structures."
                what_to_investigate = "Compare margin stability against direct peers who may have faced industry-wide cost fluctuations."
            
            op_bps = latest_der.operating_margin_change_bps
            op_bps_str = f"{op_bps:+.0f} bps" if op_bps is not None else "N/A"
            op_lev = latest_der.operating_leverage
            op_lev_str = f"{op_lev:+.1f}% spread" if op_lev is not None else "N/A"
            margins = [d.operating_margin for d in derived]
            margin_vol = calculate_margin_volatility(margins)
            margin_vol_str = f"{margin_vol:.2f}%" if margin_vol is not None else "N/A"

            evidence = (
                f"Operating Margin: {curr_op_margin:.2f}% in {latest_der.fiscal_year_label} vs "
                f"{prior_op_margin:.2f}% in {prior_der.fiscal_year_label} (Delta: {margin_delta:+.2f} pts / {op_bps_str}). "
                f"Operating Leverage: {op_lev_str} | 5-Yr Margin Volatility (std dev): {margin_vol_str}. Net Margin: {latest_der.net_margin:.2f}%."
            )
        else:
            headline = f"Operating Margin Reported at {curr_op_margin:.1f}%"
            what_changed = f"Operating margin stood at {curr_op_margin:.1f}% in {latest_der.fiscal_year_label}."
            evidence = f"Operating Income: {latest_fact.operating_income:,.0f} {latest_fact.unit} on Revenue: {latest_fact.revenue:,.0f} {latest_fact.unit}."
            why_it_matters = "Establishes baseline operational profitability."
            what_to_investigate = "Monitor trends across subsequent quarters."

        limitations = "Operating income excludes financing expenses and corporate tax rates, but may include exceptional restructuring items."
        if latest_fact.comparability_flag == "PROXY" or "Proxy" in (latest_fact.accounting_notes or ""):
            proxy_detail = latest_fact.accounting_notes if latest_fact.accounting_notes else "PBEI / EBITDA proxy"
            headline += f" (Proxy Basis)"
            evidence += f" [Note: Operating income utilizes a proxy definition: {proxy_detail}]."
            limitations += f" Operating profit utilizes a {latest_fact.comparability_flag} basis ({proxy_detail}); derived margins and operating leverage reflect this proxy."

        return FinancialInsight(
            category="OPERATING_MARGINS",
            headline=headline,
            what_changed=what_changed,
            evidence=evidence,
            why_it_matters=why_it_matters,
            what_to_investigate=what_to_investigate,
            limitations=limitations
        )

    @staticmethod
    def _analyze_cash_flow(
        facts: List[FinancialFact], 
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        latest_fact = facts[-1]
        latest_der = derived[-1]
        prior_der = derived[-2] if len(derived) >= 2 else None

        unit = latest_fact.unit
        fcf = latest_der.free_cash_flow
        ocf = latest_fact.operating_cash_flow
        capex = latest_fact.capital_expenditure

        if fcf is None:
            return None

        if fcf > 0:
            headline = f"Positive Free Cash Flow Generation ({fcf:,.0f} {unit})"
            what_changed = f"The business generated {fcf:,.0f} {unit} in free cash flow after funding {capex:,.0f} {unit} of capital expenditures from {ocf:,.0f} {unit} in operating cash."
            why_it_matters = "Positive free cash flow provides internal funding flexibility for debt reduction, shareholder returns, or capital reinvestment without immediate reliance on external financing."
            what_to_investigate = "Assess capital allocation priorities: check cash flow from financing activities for dividend payouts, debt amortization, or share repurchases."
        else:
            headline = f"Negative Free Cash Flow ({fcf:,.0f} {unit})"
            what_changed = f"Capital expenditure ({capex:,.0f} {unit}) exceeded operating cash flow ({ocf:,.0f} {unit}), leading to free cash flow deficit of {abs(fcf):,.0f} {unit}."
            why_it_matters = "Negative free cash flow requires funding from existing cash reserves, working capital management, or external debt/equity financing."
            what_to_investigate = "Investigate whether capex is growth-oriented (capacity expansion, technology infrastructure) or defensive maintenance."

        evidence = (
            f"Operating Cash Flow: {ocf:,.0f} {unit} | Capex: {capex:,.0f} {unit} | "
            f"Free Cash Flow: {fcf:,.0f} {unit} ({latest_fact.fiscal_year_label})."
        )
        limitations = "Free cash flow defined standardly as (Operating Cash Flow - Capex); excludes lease principal repayments."

        return FinancialInsight(
            category="CASH_GENERATION",
            headline=headline,
            what_changed=what_changed,
            evidence=evidence,
            why_it_matters=why_it_matters,
            what_to_investigate=what_to_investigate,
            limitations=limitations
        )

    @staticmethod
    def _analyze_cash_conversion(
        facts: List[FinancialFact], 
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        latest_fact = facts[-1]
        latest_der = derived[-1]
        unit = latest_fact.unit

        ratio = latest_der.cash_conversion_ratio
        reason = latest_der.cash_conversion_qualified_reason

        if ratio is None:
            headline = "Cash Conversion Ratio Suppressed Due to Low or Negative Earnings"
            what_changed = "The cash conversion ratio (OCF / Net Income) was omitted per data integrity guidelines."
            evidence = f"Net Income: {latest_fact.net_income:,.0f} {unit}, Operating Cash Flow: {latest_fact.operating_cash_flow:,.0f} {unit}. Qualification reason: {reason}."
            why_it_matters = "Computing OCF / Net Income when net income is negative or close to zero yields mathematically unstable or economically misleading metrics."
            what_to_investigate = "Analyze the operating cash flow reconciliation in the audited statement of cash flows directly to assess operating cash generation independently of net loss."
            limitations = "Suppression rule enforces analyst integrity per Fundamentals Lens methodology."
        elif ratio >= 1.0:
            headline = f"Operating Cash Conversion Above Net Income ({ratio:.2f}x)"
            what_changed = f"Operating cash flow ({latest_fact.operating_cash_flow:,.0f} {unit}) exceeded reported net income ({latest_fact.net_income:,.0f} {unit}), achieving a {ratio:.2f}x conversion."
            evidence = f"OCF / Net Income = {latest_fact.operating_cash_flow:,.0f} / {latest_fact.net_income:,.0f} = {ratio:.2f}x in {latest_fact.fiscal_year_label}."
            why_it_matters = "Operating cash flow exceeding reported net income indicates that non-cash accounting expenses (e.g. depreciation and amortization) and working capital dynamics supported operational cash generation."
            what_to_investigate = "Review changes in working capital items (receivables collections, inventory buildup, payables elongation) and non-cash items to confirm whether cash realization is recurring."
            limitations = "Conversion ratios can fluctuate due to year-end timing differences, customer advances, or inventory cycle changes."
        else:
            headline = f"Operating Cash Conversion Below Net Income ({ratio:.2f}x)"
            what_changed = f"Operating cash flow ({latest_fact.operating_cash_flow:,.0f} {unit}) lagged net income ({latest_fact.net_income:,.0f} {unit}) with a conversion ratio of {ratio:.2f}x."
            evidence = f"OCF / Net Income = {latest_fact.operating_cash_flow:,.0f} / {latest_fact.net_income:,.0f} = {ratio:.2f}x in {latest_fact.fiscal_year_label}."
            why_it_matters = "When operating cash flow trails net income (< 1.0x), accounting net income has not been fully realized as operating cash flow during the period, often due to cash absorbed into receivables or inventory."
            what_to_investigate = "Examine the statement of cash flows for increases in trade receivables (DSO trends), inventory buildup, or contract asset expansion."
            limitations = "Working capital investments in growing businesses can depress cash conversion without necessarily reflecting structural collection issues."

        return FinancialInsight(
            category="CASH_CONVERSION",
            headline=headline,
            what_changed=what_changed,
            evidence=evidence,
            why_it_matters=why_it_matters,
            what_to_investigate=what_to_investigate,
            limitations=limitations
        )

    @staticmethod
    def _analyze_capital_reinvestment(
        facts: List[FinancialFact], 
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        latest_fact = facts[-1]
        latest_der = derived[-1]
        unit = latest_fact.unit

        if latest_fact.revenue <= 0:
            return None

        capex_intensity = round((latest_fact.capital_expenditure / latest_fact.revenue) * 100.0, 1)

        if latest_fact.capital_expenditure == 0.0:
            headline = "Zero Direct Capital Expenditures Reported"
            what_changed = f"No cash expenditures for property and equipment additions were reported in {latest_fact.fiscal_year_label} investing cash flows."
            why_it_matters = "A period without direct capital additions reflects an asset-light operating model or reliance on leased facilities/equipment."
            what_to_investigate = "Review notes on leases (Ind AS 116 / ASC 842) and intangible asset additions."
        elif capex_intensity >= 15.0:
            headline = f"High Capital Intensity ({capex_intensity:.1f}% of Revenue)"
            what_changed = f"The business invested {latest_fact.capital_expenditure:,.0f} {unit} into capital assets, representing {capex_intensity:.1f}% of total annual revenue."
            why_it_matters = "High capital reinvestment reflects substantial long-term asset additions (such as datacenter, manufacturing, or vehicle fleet infrastructure) that will influence future depreciation and operating asset capacity."
            what_to_investigate = "Review management commentary on return on invested capital (ROIC) and anticipated commercialization timelines."
        elif capex_intensity <= 3.0:
            headline = f"Asset-Light Reinvestment Model ({capex_intensity:.1f}% of Revenue)"
            what_changed = f"Capital expenditures required only {capex_intensity:.1f}% of revenue ({latest_fact.capital_expenditure:,.0f} {unit})."
            why_it_matters = "Asset-light business models require less capital reinvestment into physical property, plant, and equipment relative to annual revenue."
            what_to_investigate = "Check whether software capitalizations or operating leases are substituting for direct PPE additions."
        else:
            headline = f"Moderate Reinvestment Rate ({capex_intensity:.1f}% of Revenue)"
            what_changed = f"Capital expenditure stood at {latest_fact.capital_expenditure:,.0f} {unit} ({capex_intensity:.1f}% of revenue)."
            why_it_matters = "Reflects standard ongoing maintenance and selective capacity growth."
            what_to_investigate = "Compare against peer capital reinvestment rates across the cycle."

        cum_flows = calculate_cumulative_cash_flows(facts)
        cum_reinvest_pct = cum_flows.get("cumulative_reinvestment_pct")
        reinvest_str = f"{cum_reinvest_pct:.1f}%" if cum_reinvest_pct is not None else "N/A"
        cum_ocf = cum_flows.get("cumulative_ocf", 0.0)
        cum_capex = cum_flows.get("cumulative_capex", 0.0)
        cum_fcf = cum_flows.get("cumulative_fcf", 0.0)

        evidence = (
            f"Capex: {latest_fact.capital_expenditure:,.0f} {unit} on Revenue: {latest_fact.revenue:,.0f} {unit} = {capex_intensity:.1f}% Capex Intensity ({latest_fact.fiscal_year_label}). "
            f"5-Year Cumulative OCF: {cum_ocf:,.0f} {unit} | Capex: {cum_capex:,.0f} {unit} | FCF: {cum_fcf:,.0f} {unit} | Cumulative Reinvestment: {reinvest_str} of OCF."
        )
        limitations = "Capex reflects cash outflows for property, plant, and equipment; does not include R&D expensed directly on the income statement."

        return FinancialInsight(
            category="CAPITAL_INTENSITY",
            headline=headline,
            what_changed=what_changed,
            evidence=evidence,
            why_it_matters=why_it_matters,
            what_to_investigate=what_to_investigate,
            limitations=limitations
        )
