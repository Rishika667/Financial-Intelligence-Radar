"""
Rule-based analytical narrative engine for Fundamentals Lens.
Generates deterministic, evidence-linked insights:
'What changed, why it matters, and what to investigate'
"""
from dataclasses import dataclass
from typing import List, Optional, Dict, Any
from .models import FinancialFact, DerivedMetrics
from .metrics import compute_derived_metrics_for_company


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

        if derived is None:
            derived = compute_derived_metrics_for_company(facts)

        insights: List[FinancialInsight] = []

        # 1. Revenue Trajectory Insight
        rev_insight = cls._analyze_revenue_trajectory(facts, derived)
        if rev_insight:
            insights.append(rev_insight)

        # 2. Operating Margin & Profitability Insight
        margin_insight = cls._analyze_margin_trajectory(facts, derived)
        if margin_insight:
            insights.append(margin_insight)

        # 3. Cash Flow Generation & Free Cash Flow Insight
        cash_insight = cls._analyze_cash_flow(facts, derived)
        if cash_insight:
            insights.append(cash_insight)

        # 4. Earnings Quality & Cash Conversion Insight
        conv_insight = cls._analyze_cash_conversion(facts, derived)
        if conv_insight:
            insights.append(conv_insight)

        # 5. Capital Intensity & Reinvestment
        capex_insight = cls._analyze_capital_reinvestment(facts, derived)
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
        total_growth_pct = round(((latest_rev - first_rev) / first_rev) * 100.0, 1)

        latest_growth = latest_derived.revenue_growth_yoy
        prior_growth = prior_derived.revenue_growth_yoy if prior_derived else None
        growth_str = f"{latest_growth:+.1f}%" if latest_growth is not None else "N/A"

        if latest_growth is not None and latest_growth > 15.0:
            headline = f"Strong Revenue Expansion ({latest_growth:+.1f}% YoY)"
            what_changed = f"Revenue grew by {latest_growth:+.1f}% in {latest_fact.fiscal_year_label}, expanding from {first_rev:,.0f} {unit} in {first_fact.fiscal_year_label} to {latest_rev:,.0f} {unit} in {latest_fact.fiscal_year_label}."
            why_it_matters = "Double-digit top-line growth may reflect expanding customer demand, market share gains, price increases, or scope changes such as consolidation."
            what_to_investigate = "Determine the balance between organic volume expansion, price realization, foreign exchange effects, and inorganic acquisition contributions."
        elif latest_growth is not None and latest_growth < 0.0:
            headline = f"Revenue Contraction Detected ({latest_growth:.1f}% YoY)"
            what_changed = f"Top-line revenue contracted by {abs(latest_growth):.1f}% in {latest_fact.fiscal_year_label} to {latest_rev:,.0f} {unit}."
            why_it_matters = "Top-line contraction can pressure operating leverage and reduce absorption of fixed overheads."
            what_to_investigate = "Check product line segment disclosures, foreign currency translation impacts, and industry cyclicality factors."
        else:
            headline = f"Moderate Top-Line Growth ({growth_str} YoY)"
            what_changed = f"Revenue shifted by {growth_str} in {latest_fact.fiscal_year_label}, reflecting a {total_growth_pct:+.1f}% 5-year cumulative change."
            why_it_matters = "Steady single-digit expansion reflects mature market positioning or stable market share retention."
            what_to_investigate = "Examine geographic and product-mix variations that may diverge from the consolidated growth rate."

        evidence = (
            f"5-Year Revenue: {first_rev:,.0f} {unit} ({first_fact.fiscal_year_label}) -> "
            f"{latest_rev:,.0f} {unit} ({latest_fact.fiscal_year_label}) [{total_growth_pct:+.1f}% overall]. "
            f"Latest YoY Growth: {growth_str}."
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
                why_it_matters = "Margin expansion may suggest operating leverage, lower input costs, favorable pricing, or a shift toward higher-margin products/services."
                what_to_investigate = "Investigate whether gross margins expanded or whether operating expenses (SG&A/R&D) grew at a slower rate than revenue."
            elif margin_delta <= -1.0:
                headline = f"Operating Margin Compression ({margin_delta:.2f} percentage points)"
                what_changed = f"Operating margin declined from {prior_op_margin:.1f}% in {prior_der.fiscal_year_label} to {curr_op_margin:.1f}% in {latest_der.fiscal_year_label}."
                why_it_matters = "Margin compression may indicate increased production costs, competitive pricing pressure, or planned overhead investments ahead of revenue."
                what_to_investigate = "Check gross margin vs. SG&A breakdown in the notes to the financial statements to isolate the cost driver."
            else:
                headline = f"Stable Operating Profitability ({curr_op_margin:.1f}% margin)"
                what_changed = f"Operating margin held steady at {curr_op_margin:.1f}% (change of {margin_delta:+.2f} percentage points YoY)."
                why_it_matters = "Predictable operating margins highlight disciplined cost control and consistent operational execution."
                what_to_investigate = "Compare margin stability against direct peers who may have faced industry-wide cost fluctuations."
            
            evidence = (
                f"Operating Margin: {curr_op_margin:.2f}% in {latest_der.fiscal_year_label} vs "
                f"{prior_op_margin:.2f}% in {prior_der.fiscal_year_label} (Delta: {margin_delta:+.2f} pts). "
                f"Net Margin: {latest_der.net_margin:.2f}%."
            )
        else:
            headline = f"Operating Margin Reported at {curr_op_margin:.1f}%"
            what_changed = f"Operating margin stood at {curr_op_margin:.1f}% in {latest_der.fiscal_year_label}."
            evidence = f"Operating Income: {latest_fact.operating_income:,.0f} {latest_fact.unit} on Revenue: {latest_fact.revenue:,.0f} {latest_fact.unit}."
            why_it_matters = "Establishes baseline operational profitability."
            what_to_investigate = "Monitor trends across subsequent quarters."

        limitations = "Operating income excludes financing expenses and corporate tax rates, but may include exceptional restructuring items."

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

        if capex_intensity >= 15.0:
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

        evidence = f"Capex: {latest_fact.capital_expenditure:,.0f} {unit} on Revenue: {latest_fact.revenue:,.0f} {unit} = {capex_intensity:.1f}% Capex Intensity ({latest_fact.fiscal_year_label})."
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
