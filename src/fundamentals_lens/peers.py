"""
Peer comparison engine and analytical safeguards for Fundamentals Lens.
Provides defensible peer metrics, comparability caveats, and currency guards.
"""
from dataclasses import dataclass
from typing import List, Dict, Any, Optional
from .models import Company, FinancialFact, DerivedMetrics
from .metrics import compute_derived_metrics_for_company


@dataclass
class PeerGroupMetadata:
    group_id: str
    group_name: str
    currency: str
    standard_unit: str
    companies: List[str]
    comparability_notes: str
    structural_caveats: List[str]


PEER_GROUP_METADATA: Dict[str, PeerGroupMetadata] = {
    "group_a_tech": PeerGroupMetadata(
        group_id="group_a_tech",
        group_name="Global Technology Leaders",
        currency="USD",
        standard_unit="$ Millions",
        companies=["AAPL", "MSFT", "GOOGL"],
        comparability_notes=(
            "Leading global digital technology companies with high operating cash flows and significant market scale. "
            "However, business models differ fundamentally between consumer hardware/services ecosystem (Apple), "
            "enterprise cloud/productivity software (Microsoft), and digital search/advertising infrastructure (Alphabet)."
        ),
        structural_caveats=[
            "Differing Fiscal Year-Ends: Apple (late September), Microsoft (June 30), and Alphabet (December 31). Periods compare closest corresponding annual cycles.",
            "Capital Intensity Divergence: Alphabet and Microsoft incur massive hyperscaler datacenter capex ($40B–$115B+), whereas Apple operates a leaner outsourced manufacturing model.",
            "R&D Accounting: All three expense software R&D immediately on the income statement."
        ]
    ),
    "group_b_india_it": PeerGroupMetadata(
        group_id="group_b_india_it",
        group_name="Indian IT Services",
        currency="INR",
        standard_unit="\u20b9 Crores",
        companies=["TCS", "INFY", "HCLTECH"],
        comparability_notes=(
            "Directly comparable tier-1 global IT consulting and systems integration service providers. "
            "All three share identical March 31 fiscal year-ends, Ind AS / IFRS accounting frameworks, "
            "asset-light operating structures, low financial leverage, and high free cash flow conversion."
        ),
        structural_caveats=[
            "High Comparability: Uniform March 31 fiscal cycle and offshore delivery business models.",
            "Delivery Mix: Minor variations in client vertical concentration (BFSI vs. manufacturing vs. life sciences).",
            "M&A and Intangibles: HCLTech carries higher amortisation from past IP/software product carve-outs."
        ]
    ),
    "group_c_india_fmcg": PeerGroupMetadata(
        group_id="group_c_india_fmcg",
        group_name="Indian Consumer Brands (FMCG)",
        currency="INR",
        standard_unit="\u20b9 Crores",
        companies=["HINDUNILVR", "BRITANNIA", "DABUR"],
        comparability_notes=(
            "Prominent Indian fast-moving consumer goods manufacturers with widespread direct retail distribution. "
            "All three report on a March 31 financial year under Ind AS with stable consumer demand moats."
        ),
        structural_caveats=[
            "Working Capital Cycles: HUL operates on a negative working capital cycle with significant vendor credit, whereas Britannia and Dabur maintain more traditional distribution credit terms.",
            "Raw Material Inflation: Exposure differs by category—Britannia is sensitive to wheat, palm oil, and sugar; HUL to crude derivatives and palm oil; Dabur to agricultural herbs and packaging.",
            "Scale Differential: HUL operates at roughly 3.3x the revenue scale of Britannia and 4.8x of Dabur."
        ]
    ),
    "group_d_india_auto": PeerGroupMetadata(
        group_id="group_d_india_auto",
        group_name="Indian Auto & Mobility",
        currency="INR",
        standard_unit="\u20b9 Crores",
        companies=["MARUTI", "BAJAJ-AUTO", "HEROMOTOCO"],
        comparability_notes=(
            "Prominent Indian automotive manufacturers with high brand recognition. "
            "CRITICAL CAVEAT: Passenger car economics differ structurally from two- and three-wheeler economics."
        ),
        structural_caveats=[
            "Product Segment Incomparability: Maruti Suzuki produces 4-wheeler passenger cars with higher average selling prices (ASP), distinct supply chains, and large recurring tooling capex.",
            "Two-Wheeler Dynamics: Bajaj Auto and Hero MotoCorp manufacture 2-wheelers, with Bajaj also producing 3-wheeler commercial vehicles.",
            "Geographic Exposure: Bajaj Auto generates ~40% of volumes from international exports (Africa, LatAm, ASEAN), whereas Hero MotoCorp and Maruti Suzuki are primarily domestic Indian market focused.",
            "Avoid Direct Cross-Segment Ranking: Compare margin trends and cash generation, but do not infer operating superiority without adjusting for segment economics."
        ]
    ),
    "group_e_us_retail": PeerGroupMetadata(
        group_id="group_e_us_retail",
        group_name="US Retailers",
        currency="USD",
        standard_unit="$ Millions",
        companies=["WMT", "COST", "TGT"],
        comparability_notes=(
            "Large-scale US retail enterprises serving millions of daily consumers. "
            "However, operating profit structures differ substantially across business models."
        ),
        structural_caveats=[
            "Membership Club Model (Costco): Sells merchandise at near cost (gross margin ~11%–12%) and generates the majority of operating income from recurring, high-margin membership fees ($5.9B in FY26).",
            "Omni-Channel Supercenter Model (Walmart): Massive global grocery and general merchandise scale ($713B+ revenue) with growing digital marketplace and advertising revenues.",
            "Discretionary & Style Focus (Target): More heavily weighted toward apparel, home decor, and beauty, resulting in higher gross margin potential but greater vulnerability to consumer discretionary pullbacks.",
            "Fiscal Calendar Differences: Walmart and Target end their fiscal years on the Saturday nearest January 31, while Costco ends in late August / early September."
        ]
    )
}


class PeerComparisonEngine:
    """
    Engine to build consistent, guarded peer comparisons across financial metrics.
    """

    @classmethod
    def get_peer_group_info(cls, group_id: str) -> Optional[PeerGroupMetadata]:
        return PEER_GROUP_METADATA.get(group_id)

    @classmethod
    def get_all_peer_groups(cls) -> Dict[str, PeerGroupMetadata]:
        return PEER_GROUP_METADATA

    @classmethod
    def build_peer_comparison_matrix(
        cls,
        companies: List[Company],
        facts_by_ticker: Dict[str, List[FinancialFact]],
        group_id: str,
        metric_name: str
    ) -> Dict[str, Any]:
        """
        Builds a multi-period matrix for peer comparison with unit guards.
        Supported metrics: 'revenue', 'revenue_growth_yoy', 'operating_margin', 
                           'net_margin', 'free_cash_flow', 'cash_conversion_ratio'
        """
        group_meta = cls.get_peer_group_info(group_id)
        group_companies = [c for c in companies if c.peer_group_id == group_id]

        if not group_companies or not group_meta:
            return {"error": f"Invalid peer group: {group_id}"}

        # Guard: Check for currency uniformity
        currencies = {c.reporting_currency for c in group_companies}
        is_single_currency = len(currencies) == 1
        currency_code = list(currencies)[0] if is_single_currency else "MIXED"

        # Determine metric metadata
        percentage_metrics = {"revenue_growth_yoy", "operating_margin", "net_margin"}
        ratio_metrics = {"cash_conversion_ratio"}
        nominal_metrics = {"revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure", "free_cash_flow"}

        if metric_name in percentage_metrics:
            unit_display = "%"
        elif metric_name in ratio_metrics:
            unit_display = "Ratio (x)"
        else:
            unit_display = group_meta.standard_unit if is_single_currency else "Local Currencies"

        metric_note = None
        if metric_name == "operating_income":
            metric_note = (
                "Accounting Definition Note: US peers report US GAAP Operating Income; Indian IT peers report Ind AS EBIT; "
                "Indian FMCG and Auto peers report Profit Before Exceptional Items (PBEI). Direct rankings should account for these standards."
            )
        elif metric_name == "capital_expenditure":
            metric_note = (
                "Accounting Definition Note: Capex reflects cash outflows for Property, Plant, and Equipment (PPE additions) "
                "from Investing Activities; certain Indian disclosures include capital work-in-progress (CWIP) or intangible asset additions."
            )

        series_data = []

        for c in group_companies:
            c_facts = sorted(facts_by_ticker.get(c.ticker, []), key=lambda x: x.fiscal_year)
            c_derived = compute_derived_metrics_for_company(c_facts)
            derived_map = {d.fiscal_year: d for d in c_derived}
            facts_map = {f.fiscal_year: f for f in c_facts}

            data_points = []
            for f in c_facts:
                yr = f.fiscal_year
                d = derived_map.get(yr)
                val = None

                if metric_name in ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"):
                    val = getattr(f, metric_name, None)
                elif metric_name == "revenue_growth_yoy":
                    val = d.revenue_growth_yoy if d else None
                elif metric_name == "operating_margin":
                    val = d.operating_margin if d else None
                elif metric_name == "net_margin":
                    val = d.net_margin if d else None
                elif metric_name == "free_cash_flow":
                    val = d.free_cash_flow if d else None
                elif metric_name == "cash_conversion_ratio":
                    val = d.cash_conversion_ratio if d else None

                data_points.append({
                    "fiscal_year": yr,
                    "fiscal_year_label": f.fiscal_year_label,
                    "value": val
                })

            series_data.append({
                "ticker": c.ticker,
                "company_name": c.name,
                "currency": c.reporting_currency,
                "data": data_points
            })

        return {
            "group_id": group_id,
            "group_name": group_meta.group_name,
            "metric_name": metric_name,
            "metric_note": metric_note,
            "unit": unit_display,
            "is_single_currency": is_single_currency,
            "currency_code": currency_code,
            "comparability_notes": group_meta.comparability_notes,
            "structural_caveats": group_meta.structural_caveats,
            "series": series_data
        }

    @classmethod
    def build_indexed_peer_matrix(
        cls,
        companies: List[Company],
        facts_by_ticker: Dict[str, List[FinancialFact]],
        group_id: str,
        metric_name: str,
        base_year: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Builds an indexed comparison matrix where performance is normalized to 100.0
        at a designated base year (or earliest available period).
        Formula: Indexed_t = (Metric_t / Metric_{base}) * 100.0.
        If Metric_{base} <= 0 or missing, indexing is suppressed with an explicit warning.
        """
        matrix = cls.build_peer_comparison_matrix(companies, facts_by_ticker, group_id, metric_name)
        if "error" in matrix:
            return matrix

        # Collect all available fiscal years across series
        all_years = []
        series_years = []
        for s in matrix["series"]:
            years_for_s = {
                pt["fiscal_year"] for pt in s["data"]
                if pt.get("fiscal_year") is not None and pt.get("value") is not None
            }
            if years_for_s:
                series_years.append(years_for_s)
                all_years.extend(list(years_for_s))
        
        if not all_years:
            return {"error": "No historical periods with valid data found for indexed comparison."}

        common_years = set.intersection(*series_years) if series_years else set()

        if base_year is not None:
            base_year_used = base_year
        elif common_years:
            base_year_used = min(common_years)
        else:
            base_year_used = min(all_years)

        base_period_label = None

        indexed_series = []
        for s in matrix["series"]:
            base_pt = next((pt for pt in s["data"] if pt.get("fiscal_year") == base_year_used), None)
            base_val = base_pt["value"] if base_pt else None
            if base_pt and base_period_label is None:
                base_period_label = base_pt.get("fiscal_year_label", str(base_year_used))

            suppressed = False
            suppress_reason = None

            if base_val is None:
                suppressed = True
                suppress_reason = f"Base period ({base_year_used}) value is unavailable."
            elif base_val <= 0:
                suppressed = True
                suppress_reason = f"Base period value ({base_val}) is non-positive; indexing suppressed to avoid direction distortion."

            indexed_data = []
            for pt in s["data"]:
                val = pt["value"]
                if suppressed or val is None or base_val is None or base_val == 0:
                    idx_val = None
                else:
                    idx_val = round((val / base_val) * 100.0, 2)

                indexed_data.append({
                    "fiscal_year": pt["fiscal_year"],
                    "fiscal_year_label": pt["fiscal_year_label"],
                    "value": idx_val,
                    "nominal_value": val
                })

            indexed_series.append({
                "ticker": s["ticker"],
                "company_name": s["company_name"],
                "currency": s["currency"],
                "is_suppressed": suppressed,
                "suppress_reason": suppress_reason,
                "base_year": base_year_used,
                "base_value": base_val,
                "data": indexed_data
            })

        caveats = list(matrix["structural_caveats"])
        caveats.append(
            f"Indexed growth normalizes the base period ({base_period_label or base_year_used} = 100.0) "
            "to show relative trajectories. It does NOT compare absolute corporate scale or financial magnitude."
        )

        return {
            "group_id": group_id,
            "group_name": matrix["group_name"],
            "metric_name": metric_name,
            "unit": f"Index (Base {base_period_label or base_year_used} = 100.0)",
            "base_year": base_year_used,
            "base_period_label": base_period_label or str(base_year_used),
            "is_single_currency": matrix["is_single_currency"],
            "currency_code": matrix["currency_code"],
            "comparability_notes": matrix["comparability_notes"],
            "structural_caveats": caveats,
            "series": indexed_series
        }

