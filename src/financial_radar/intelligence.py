import json

def _pct(curr, prev):
    if prev is not None and prev != 0 and curr is not None:
        return f"{((curr - prev) / abs(prev)) * 100:.1f}%"
    return "N/A"

def generate_intelligence(signal_id, company, sector, evidence):
    try:
        ev = json.loads(evidence) if isinstance(evidence, str) else (evidence or [])
    except Exception:
        ev = []
    
    # helper for 2-metric comparison
    def get_4(ev):
        if len(ev) >= 4:
            return ev[0].get("value"), ev[1].get("value"), ev[2].get("value"), ev[3].get("value")
        return None, None, None, None

    if signal_id == "RECEIVABLES_REVENUE_DIVERGENCE":
        what = "Accounts receivable grew materially faster than revenue."
        curr_ar, curr_rev, prev_ar, prev_rev = get_4(ev)
        if curr_ar is not None:
            ar_pct = _pct(curr_ar, prev_ar)
            rev_pct = _pct(curr_rev, prev_rev)
            if ar_pct != "N/A" and rev_pct != "N/A":
                what = f"Accounts receivable changed by {ar_pct} while revenue changed by {rev_pct}."
        
        return {
            "title": "Working-Capital Divergence",
            "what_changed": what,
            "why_it_matters": "Receivables are growing faster than reported revenue, which can increase working-capital requirements and warrants review of collections, payment terms, customer mix, and revenue-related disclosures.",
            "investigate": [
                "DSO trend",
                "customer concentration",
                "payment terms",
                "contract changes",
                "relevant filing disclosures"
            ]
        }
    elif signal_id == "INVENTORY_SALES_DIVERGENCE":
        what = "Inventory grew materially faster than sales."
        curr_inv, curr_rev, prev_inv, prev_rev = get_4(ev)
        if curr_inv is not None:
            inv_pct = _pct(curr_inv, prev_inv)
            rev_pct = _pct(curr_rev, prev_rev)
            if inv_pct != "N/A" and rev_pct != "N/A":
                what = f"Inventory changed by {inv_pct} while sales changed by {rev_pct}."
        
        return {
            "title": "Inventory Divergence",
            "what_changed": what,
            "why_it_matters": "Inventory is growing faster than sales, which can indicate slowing demand, product mix changes, or supply chain bottlenecks.",
            "investigate": [
                "inventory days outstanding",
                "product obsolescence risks",
                "future discounting and margin pressure",
                "supply chain planning vs actual demand"
            ]
        }
    elif signal_id == "GROSS_MARGIN_COMPRESSION":
        return {
            "title": "Gross Margin Compression",
            "what_changed": "Gross margin declined period-over-period.",
            "why_it_matters": "A declining gross margin points to increased cost of goods sold, supply chain cost inflation, or constrained pricing power.",
            "investigate": [
                "input cost inflation (materials, labor, freight)",
                "pricing power constraints",
                "product mix shift toward lower-margin segments",
                "inventory write-downs"
            ]
        }
    elif signal_id == "OPERATING_DELEVERAGE":
        return {
            "title": "Operating Deleverage",
            "what_changed": "Operating margin deteriorated.",
            "why_it_matters": "Highlights structurally higher operating expenses relative to revenue generation.",
            "investigate": [
                "SG&A expense growth vs revenue growth",
                "R&D spend efficiency",
                "one-time vs recurring structural costs",
                "fixed cost deleverage"
            ]
        }
    elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
        return {
            "title": "Cash Conversion Decline",
            "what_changed": "Operating cash flow declined relative to net income.",
            "why_it_matters": "Points to lower quality of earnings supported by non-cash accruals or working capital drag.",
            "investigate": [
                "non-cash earnings quality",
                "working capital drag (receivables, inventory)",
                "capitalized expenses",
                "timing of cash receipts/disbursements"
            ]
        }
    elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
        return {
            "title": "Free Cash Flow Deterioration",
            "what_changed": "Free cash flow declined materially.",
            "why_it_matters": "Reduces capital available for debt service, dividends, or reinvestment.",
            "investigate": [
                "capex cycle vs maintenance capex",
                "operating cash flow weakness",
                "dividend/buyback sustainability",
                "debt service capacity"
            ]
        }
    elif signal_id == "DEBT_OPERATING_INCOME_DETERIORATION":
        return {
            "title": "Leverage / Interest Burden Increase",
            "what_changed": "Debt increased relative to operating income.",
            "why_it_matters": "Increases financial risk and debt service burden relative to core operating profitability.",
            "investigate": [
                "refinancing risk and maturity wall",
                "interest rate exposure (fixed vs floating)",
                "covenant headroom",
                "use of proceeds for new debt"
            ]
        }
    elif signal_id == "LIQUIDITY_COMPRESSION":
        return {
            "title": "Liquidity Compression",
            "what_changed": "Cash reserves declined relative to current liabilities.",
            "why_it_matters": "Signals potential short-term funding pressure and tightening working capital.",
            "investigate": [
                "short-term funding needs",
                "working capital constraints",
                "revolver capacity",
                "upcoming near-term maturities"
            ]
        }
    elif signal_id == "SHARE_COUNT_DILUTION":
        what = "Diluted share count increased."
        if len(ev) >= 2:
            curr, prev = ev[0].get("value"), ev[1].get("value")
            if curr is not None and prev is not None and prev != 0:
                pct = ((curr - prev) / abs(prev)) * 100
                what = f"Diluted share count increased by {pct:.1f}%."

        return {
            "title": "Share Count Dilution",
            "what_changed": what,
            "why_it_matters": "Directly dilutes existing shareholder equity and EPS.",
            "investigate": [
                "stock-based compensation (SBC) levels",
                "secondary equity offerings",
                "convertible debt dilution",
                "acquisition currency usage"
            ]
        }
    elif signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER":
        return {
            "title": "Multi-Factor Deterioration Cluster",
            "what_changed": "3 or more fundamental deterioration signals fired simultaneously.",
            "why_it_matters": "Indicates broad structural deterioration across multiple operational and financial dimensions.",
            "investigate": [
                "broad fundamental inflection point",
                "management execution across multiple fronts",
                "macro/sector headwinds impacting multiple metrics",
                "review all underlying component signals"
            ]
        }
    return {
        "title": signal_id.replace("_", " ", -1).title(),
        "what_changed": "Metric triggered predefined deterioration thresholds.",
        "why_it_matters": "Requires standard analyst review to determine drivers of the variation.",
        "investigate": ["review underlying SEC filings and evidence"]
    }
