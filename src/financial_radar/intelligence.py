import json
import logging

logger = logging.getLogger(__name__)

def generate_intelligence(signal_id, company, sector, evidence_str):
    ev = []
    try:
        if evidence_str:
            ev = json.loads(evidence_str)
    except json.JSONDecodeError:
        pass

    what = "Metric triggered predefined deterioration thresholds."
    
    if ev and len(ev) >= 2:
        curr = ev[0].get("value")
        prev = ev[1].get("value")
        if curr is not None and prev is not None:
            if "MARGIN" in signal_id:
                what = f"{signal_id.replace('_', ' ').title().split(' ')[0]} margin declined from {prev*100:.1f}% to {curr*100:.1f}%, a {(prev-curr)*100:.1f} percentage-point decline."
            elif "DIVERGENCE" in signal_id:
                what = f"Target metric grew to {curr:,.0f} compared to {prev:,.0f} in prior period."
            elif "SHARE" in signal_id:
                pct = ((curr - prev) / prev) * 100 if prev != 0 else 0
                what = f"Diluted share count increased by {pct:.1f}% from {prev:,.0f} to {curr:,.0f}."
            elif "DEBT" in signal_id:
                what = f"Debt/operating-income increased from {prev:.2f}x to {curr:.2f}x."

    if signal_id == "RECEIVABLES_REVENUE_DIVERGENCE":
        return {
            "title": "Working-Capital Divergence",
            "what_changed": what,
            "why_it_matters": "Receivables are growing faster than reported revenue, which can increase working-capital requirements and warrants review of collections, payment terms, customer mix, and revenue-related disclosures.",
            "investigate": [
                "Review revenue recognition footnotes.",
                "Check Days Sales Outstanding (DSO) trends.",
                "Examine management commentary on customer payment terms."
            ]
        }
    elif signal_id == "INVENTORY_SALES_DIVERGENCE":
        return {
            "title": "Inventory Divergence",
            "what_changed": what,
            "why_it_matters": "Inventory is growing faster than sales, which warrants review of demand, product mix changes, or supply chain dynamics.",
            "investigate": [
                "Check for inventory obsolescence reserves.",
                "Review management discussion on supply chain or demand shifts."
            ]
        }
    elif signal_id == "GROSS_MARGIN_COMPRESSION":
        return {
            "title": "Gross Margin Compression",
            "what_changed": what,
            "why_it_matters": "A declining gross margin warrants review of increased cost of goods sold, supply chain cost inflation, or constrained pricing power.",
            "investigate": [
                "Review pricing power disclosures.",
                "Examine input cost or labor inflation notes."
            ]
        }
    elif signal_id == "OPERATING_MARGIN_DETERIORATION":
        return {
            "title": "Operating Margin Deterioration",
            "what_changed": what,
            "why_it_matters": "Operating profitability declined relative to revenue. The metric alone does not establish the underlying cause.",
            "investigate": [
                "Review SG&A expense components.",
                "Check for restructuring or impairment charges.",
                "Analyze segment-level profitability."
            ]
        }
    elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
        return {
            "title": "Cash Conversion Decline",
            "what_changed": what,
            "why_it_matters": "A lower cash conversion ratio warrants review of non-cash accruals or working capital drag.",
            "investigate": [
                "Review working capital changes.",
                "Examine non-cash adjustments to net income."
            ]
        }
    elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
        return {
            "title": "Free Cash Flow Deterioration",
            "what_changed": what,
            "why_it_matters": "Reduces capital available for debt service, dividends, or reinvestment.",
            "investigate": [
                "Review capital expenditure trends.",
                "Check operating cash flow drivers."
            ]
        }
    elif signal_id == "DEBT_OPERATING_INCOME_DETERIORATION":
        return {
            "title": "Debt to Operating Income Deterioration",
            "what_changed": what,
            "why_it_matters": "Indicates higher debt relative to core operating profitability.",
            "investigate": [
                "Review recent debt issuance or M&A.",
                "Check debt maturity profile and interest rates."
            ]
        }
    elif signal_id == "LIQUIDITY_COMPRESSION":
        return {
            "title": "Liquidity Compression",
            "what_changed": what,
            "why_it_matters": "Signals potential short-term funding pressure and tightening working capital.",
            "investigate": [
                "Review short-term debt maturities.",
                "Check cash flow from operations."
            ]
        }
    elif signal_id == "SHARE_COUNT_DILUTION":
        return {
            "title": "Share Count Increase",
            "what_changed": what,
            "why_it_matters": "Weighted-average diluted share count increased, creating per-share dilution pressure.",
            "investigate": [
                "Review recent equity issuances.",
                "Check for stock-based compensation effects.",
                "Analyze convertible debt conversions."
            ]
        }
    elif signal_id == "MULTI_FACTOR_DETERIORATION":
        return {
            "title": "Multi-Factor Deterioration Cluster",
            "what_changed": "3 or more fundamental deterioration signals fired simultaneously.",
            "why_it_matters": "Indicates broad structural deterioration across multiple operational and financial dimensions.",
            "investigate": [
                "Review the comprehensive earnings release.",
                "Check management guidance and strategic updates."
            ]
        }

    return {
        "title": signal_id.replace("_", " ").title(),
        "what_changed": "Metric triggered predefined deterioration thresholds.",
        "why_it_matters": "Requires standard analyst review to determine drivers of the variation.",
        "investigate": ["review underlying SEC filings and evidence"]
    }
