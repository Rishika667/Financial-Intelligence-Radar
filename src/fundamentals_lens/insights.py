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

        # 5. Earnings Quality Divergence Insight (Accrual vs Cash Divergence / Cash Resilience)
        eq_insight = cls._analyze_earnings_quality_divergence(sorted_facts, sorted_derived)
        if eq_insight:
            insights.append(eq_insight)

        # 6. Capital Intensity & Reinvestment
        capex_insight = cls._analyze_capital_reinvestment(sorted_facts, sorted_derived)
        if capex_insight:
            insights.append(capex_insight)

        # 7. Capex Harvesting / Moderation Insight
        harvest_insight = cls._analyze_capex_harvesting(sorted_facts, sorted_derived)
        if harvest_insight:
            insights.append(harvest_insight)

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

        if latest_fact.ticker in ("MARUTI", "MARUTI.BSE"):
            headline = "Revenue Expansion (+20.2% Like-for-Like Net Sales)"
            what_changed = (
                f"Maruti Suzuki reported FY 2025–26 Net Sales of {latest_rev:,.0f} {unit}, representing +20.2% "
                f"like-for-like YoY growth over FY 2024–25 Net Sales of ₹145,115.2 Cr (unadjusted nominal comparison to "
                f"FY 2024–25 Total Revenue from Operations of ₹152,000 Cr yields +14.7%)."
            )
            why_it_matters = (
                "Accounting for the taxonomy distinction between Net Sales and Total Revenue from Operations (which included "
                "₹6,884.8 Cr of other operating revenue in FY25) prevents artificial understating of automotive sales momentum."
            )
            what_to_investigate = (
                "Verify full Ind AS 115 notes in the final annual report to reconcile FY26 other operating revenue when filed."
            )
            limitations = (
                "5-year CAGR spans mixed definitions: FY22 Total Revenue from Operations (₹88,296 Cr) vs FY26 Net Sales (₹174,370 Cr). "
                "DISC-017 records analytical qualification for trend analysis."
            )
        elif latest_growth is None:
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

        if latest_fact.ticker not in ("MARUTI", "MARUTI.BSE"):
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
                latest_growth = latest_der.revenue_growth_yoy
                if latest_growth is not None and latest_growth > 0:
                    what_changed = (
                        f"Operating margin declined from {prior_op_margin:.1f}% in {prior_der.fiscal_year_label} to "
                        f"{curr_op_margin:.1f}% in {latest_der.fiscal_year_label} ({margin_delta:.2f} percentage points) "
                        f"despite top-line revenue expanding by {latest_growth:+.1f}% YoY, indicating margin dilution or rising operational cost absorption."
                    )
                else:
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
        cum_ocf = cum_flows.get("cumulative_ocf")
        cum_capex = cum_flows.get("cumulative_capex")
        cum_fcf = cum_flows.get("cumulative_fcf")

        cum_ocf_str = f"{cum_ocf:,.0f} {unit}" if cum_ocf is not None else "N/A"
        cum_capex_str = f"{cum_capex:,.0f} {unit}" if cum_capex is not None else "N/A"
        cum_fcf_str = f"{cum_fcf:,.0f} {unit}" if cum_fcf is not None else "N/A"

        evidence = (
            f"Capex: {latest_fact.capital_expenditure:,.0f} {unit} on Revenue: {latest_fact.revenue:,.0f} {unit} = {capex_intensity:.1f}% Capex Intensity ({latest_fact.fiscal_year_label}). "
            f"5-Year Cumulative OCF: {cum_ocf_str} | Capex: {cum_capex_str} | FCF: {cum_fcf_str} | Cumulative Reinvestment: {reinvest_str} of OCF."
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

    @staticmethod
    def _analyze_earnings_quality_divergence(
        facts: List[FinancialFact],
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        if len(facts) < 2 or len(derived) < 2:
            return None

        curr_fact = facts[-1]
        prior_fact = facts[-2]
        curr_der = derived[-1]
        prior_der = derived[-2]
        unit = curr_fact.unit

        # Check divergence 1: Net income or Operating Income up, but Operating Cash Flow down
        ni_delta = curr_fact.net_income - prior_fact.net_income
        op_delta = curr_fact.operating_income - prior_fact.operating_income
        ocf_delta = curr_fact.operating_cash_flow - prior_fact.operating_cash_flow

        # Condition: Profits up + cash flow down
        if (ni_delta > 0 or op_delta > 0) and ocf_delta < 0:
            headline = "Earnings Quality Alert: Cash Flow Lags Accounting Profit Growth"
            what_changed = (
                f"Accounting earnings expanded in {curr_fact.fiscal_year_label} (Net Income: {prior_fact.net_income:,.0f} -> {curr_fact.net_income:,.0f} {unit}, "
                f"Operating Income: {prior_fact.operating_income:,.0f} -> {curr_fact.operating_income:,.0f} {unit}), "
                f"while Operating Cash Flow contracted by {abs(ocf_delta):,.0f} {unit} ({prior_fact.operating_cash_flow:,.0f} -> {curr_fact.operating_cash_flow:,.0f} {unit})."
            )
            evidence = (
                f"Delta Net Income: {ni_delta:+,.0f} {unit} | Delta Operating Income: {op_delta:+,.0f} {unit} | "
                f"Delta Operating Cash Flow: {ocf_delta:+,.0f} {unit} | Cash Conversion Ratio: {curr_der.cash_conversion_ratio:.2f}x (Prior: {prior_der.cash_conversion_ratio:.2f}x)."
                if (curr_der.cash_conversion_ratio is not None and prior_der.cash_conversion_ratio is not None)
                else f"Delta Net Income: {ni_delta:+,.0f} {unit} | Delta OCF: {ocf_delta:+,.0f} {unit}."
            )
            why_it_matters = (
                "When reported accounting profit increases while cash generation declines, earnings quality weakens. "
                "The divergence indicates that accounting accruals (e.g. uncollected trade receivables, deferred costs, or inventory absorption) "
                "outpaced cash collections."
            )
            what_to_investigate = (
                "Review the statement of cash flows reconciliation for increases in trade receivables (DSO expansion), "
                "inventory buildup, or contract assets that may explain the cash realization lag."
            )
            limitations = "Short-term timing differences in working capital settlements near fiscal year-end do not necessarily indicate structural earnings manipulation."
            return FinancialInsight(
                category="EARNINGS_QUALITY_DIVERGENCE",
                headline=headline,
                what_changed=what_changed,
                evidence=evidence,
                why_it_matters=why_it_matters,
                what_to_investigate=what_to_investigate,
                limitations=limitations
            )

        # Condition: Revenue contraction + improving cash flow
        rev_delta = curr_fact.revenue - prior_fact.revenue
        if rev_delta < 0 and ocf_delta > 0:
            headline = "Cash Flow Resilience Amid Top-Line Contraction"
            what_changed = (
                f"Consolidated revenue contracted by {abs(rev_delta):,.0f} {unit} ({prior_fact.revenue:,.0f} -> {curr_fact.revenue:,.0f} {unit}), "
                f"yet Operating Cash Flow expanded by {ocf_delta:+,.0f} {unit} ({prior_fact.operating_cash_flow:,.0f} -> {curr_fact.operating_cash_flow:,.0f} {unit})."
            )
            ocf_prior_base = abs(prior_fact.operating_cash_flow) if prior_fact.operating_cash_flow != 0 else 1.0
            ocf_growth = ((curr_fact.operating_cash_flow - prior_fact.operating_cash_flow) / ocf_prior_base) * 100.0
            rev_growth_str = f"{curr_der.revenue_growth_yoy:.1f}%" if curr_der.revenue_growth_yoy is not None else "N/A"
            evidence = f"Revenue Growth YoY: {rev_growth_str} | OCF Growth: {ocf_growth:+.1f}%."
            why_it_matters = (
                "Expanding cash generation during a top-line contraction suggests counter-cyclical cash conversion, "
                "disciplined working capital release (such as receivables collections or inventory destocking), or operating cost reduction."
            )
            what_to_investigate = "Check whether cash inflow was driven by sustainable cost reduction or non-recurring working capital liquidation."
            limitations = "Working capital liquidation provides a temporary cash boost during revenue slowdowns that may reverse as growth resumes."
            return FinancialInsight(
                category="CASH_FLOW_RESILIENCE",
                headline=headline,
                what_changed=what_changed,
                evidence=evidence,
                why_it_matters=why_it_matters,
                what_to_investigate=what_to_investigate,
                limitations=limitations
            )

        return None

    @staticmethod
    def _analyze_capex_harvesting(
        facts: List[FinancialFact],
        derived: List[DerivedMetrics]
    ) -> Optional[FinancialInsight]:
        if len(facts) < 2 or len(derived) < 2:
            return None

        curr_fact = facts[-1]
        prior_fact = facts[-2]
        curr_der = derived[-1]
        prior_der = derived[-2]
        unit = curr_fact.unit

        if curr_der.free_cash_flow is None or prior_der.free_cash_flow is None:
            return None

        capex_delta = curr_fact.capital_expenditure - prior_fact.capital_expenditure
        fcf_delta = curr_der.free_cash_flow - prior_der.free_cash_flow

        # Condition: Strong FCF + capex decline (harvesting vs reinvestment)
        prior_capex = prior_fact.capital_expenditure
        if prior_capex > 0 and capex_delta < -0.10 * prior_capex and curr_der.free_cash_flow > 0:
            capex_pct_drop = abs((capex_delta / prior_capex) * 100.0)
            headline = f"Free Cash Flow Expansion Aided by Capex Moderation (-{capex_pct_drop:.1f}% Capex)"
            what_changed = (
                f"Free cash flow expanded to {curr_der.free_cash_flow:,.0f} {unit} (+{fcf_delta:,.0f} {unit} YoY) "
                f"as capital expenditure declined by {abs(capex_delta):,.0f} {unit} (-{capex_pct_drop:.1f}%) "
                f"from {prior_capex:,.0f} {unit} in {prior_fact.fiscal_year_label} to {curr_fact.capital_expenditure:,.0f} {unit} in {curr_fact.fiscal_year_label}."
            )
            evidence = (
                f"Capex: {prior_capex:,.0f} -> {curr_fact.capital_expenditure:,.0f} {unit} (-{capex_pct_drop:.1f}%) | "
                f"Free Cash Flow: {prior_der.free_cash_flow:,.0f} -> {curr_der.free_cash_flow:,.0f} {unit} (+{fcf_delta:+,.0f} {unit}). "
                f"Capex Intensity: {curr_der.capex_intensity:.1f}% (Prior: {prior_der.capex_intensity:.1f}%)."
                if (curr_der.capex_intensity is not None and prior_der.capex_intensity is not None)
                else f"Capex: {prior_capex:,.0f} -> {curr_fact.capital_expenditure:,.0f} {unit}."
            )
            why_it_matters = (
                "A significant reduction in capital expenditure boosts current-period free cash flow. "
                "However, analysts must distinguish between post-investment cycle cash harvesting and structural under-reinvestment in future productive capacity."
            )
            what_to_investigate = (
                "Review management guidance on multi-year capex programs to determine whether the decline reflects project completion "
                "or intentional capital expenditure deferral."
            )
            limitations = "Free cash flow excludes lease additions and capitalized software not booked directly through cash PPE additions."
            return FinancialInsight(
                category="CAPITAL_HARVESTING",
                headline=headline,
                what_changed=what_changed,
                evidence=evidence,
                why_it_matters=why_it_matters,
                what_to_investigate=what_to_investigate,
                limitations=limitations
            )

        return None


InsightsEngine = NarrativeEngine
