import json

def _pct(curr, prev):
    if prev is not None and prev != 0 and curr is not None:
        return f"{((curr - prev) / abs(prev)) * 100:.1f}%"
    return "N/A"
    
def _diff(curr, prev):
    if prev is not None and curr is not None:
        d = (curr - prev) * 100
        return f"{abs(d):.1f} percentage-point {'increase' if d > 0 else 'decline'}"
    return "N/A"

def generate_intelligence(signal_id, company, sector, evidence):
    try:
        ev = json.loads(evidence) if isinstance(evidence, str) else (evidence or [])
    except Exception:
        ev = []
    
    def get_4(ev):
        if len(ev) >= 4:
            return ev[0].get("value"), ev[1].get("value"), ev[2].get("value"), ev[3].get("value")
        return None, None, None, None
        
    def get_2(ev):
        if len(ev) >= 2:
            return ev[0].get("value"), ev[1].get("value")
        return None, None

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
            "why_it_matters": "Inventory is growing faster than sales, which warrants review of demand, product mix changes, or supply chain dynamics.",
            "investigate": [
                "inventory days outstanding",
                "product obsolescence risks",
                "future discounting and margin pressure",
                "supply chain planning vs actual demand"
            ]
        }
        
    elif signal_id == "GROSS_MARGIN_COMPRESSION":
        what = "Gross margin declined period-over-period."
        curr, prev = get_2(ev)
        if curr is not None and prev is not None:
            what = f"Gross margin changed from {prev * 100:.1f}% to {curr * 100:.1f}%, a {_diff(curr, prev)}."
            
        return {
            "title": "Gross Margin Compression",
            "what_changed": what,
            "why_it_matters": "A declining gross margin warrants review of increased cost of goods sold, supply chain cost inflation, or constrained pricing power.",
            "investigate": [
                "input cost inflation (materials, labor, freight)",
                "pricing power constraints",
                "product mix shift toward lower-margin segments",
                "inventory write-downs"
            ]
        }
        
    elif signal_id == "OPERATING_MARGIN_DETERIORATION":
        what = "Operating margin declined period-over-period."
        curr, prev = get_2(ev)
        if curr is not None and prev is not None:
            what = f"Operating margin declined from {prev * 100:.1f}% to {curr * 100:.1f}%, a {_diff(curr, prev)}."
            
        return {
            "title": "Operating Margin Deterioration",
            "what_changed": what,
            "why_it_matters": "Highlights structurally higher operating expenses relative to revenue generation.",
            "investigate": [
                "SG&A expense growth vs revenue growth",
                "R&D spend efficiency",
                "one-time vs recurring structural costs",
                "fixed cost deleverage"
            ]
        }
        
    elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
        what = "Operating cash flow declined relative to net income."
        curr_ocf, curr_ni, prev_ocf, prev_ni = get_4(ev)
        if curr_ocf is not None and curr_ni is not None and prev_ocf is not None and prev_ni is not None and curr_ni != 0 and prev_ni != 0:
            now_ratio = curr_ocf / curr_ni
            old_ratio = prev_ocf / prev_ni
            what = f"OCF/net-income declined from {old_ratio:.2f}x to {now_ratio:.2f}x."
            
        return {
            "title": "Cash Conversion Decline",
            "what_changed": what,
            "why_it_matters": "A lower cash conversion ratio warrants review of non-cash accruals or working capital drag.",
            "investigate": [
                "non-cash earnings components",
                "working capital drag (receivables, inventory)",
                "capitalized expenses",
                "timing of cash receipts/disbursements"
            ]
        }
        
    elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
        what = "Free cash flow declined materially."
        curr, prev = get_2(ev)
        if curr is not None and prev is not None:
            what = f"Free cash flow changed from {prev:,.0f} to {curr:,.0f}."
            
        return {
            "title": "Free Cash Flow Deterioration",
            "what_changed": what,
            "why_it_matters": "Reduces capital available for debt service, dividends, or reinvestment.",
            "investigate": [
                "capex cycle vs maintenance capex",
                "operating cash flow weakness",
                "dividend/buyback sustainability",
                "debt service capacity"
            ]
        }
        
    elif signal_id == "DEBT_OPERATING_INCOME_DETERIORATION":
        what = "Debt increased relative to operating income."
        curr_debt, curr_oi, prev_debt, prev_oi = get_4(ev)
        if curr_debt is not None and curr_oi is not None and prev_debt is not None and prev_oi is not None and curr_oi != 0 and prev_oi != 0:
            now_ratio = curr_debt / curr_oi
            old_ratio = prev_debt / prev_oi
            what = f"Debt/operating-income increased from {old_ratio:.2f}x to {now_ratio:.2f}x."
            
        return {
            "title": "Leverage / Interest Burden Increase",
            "what_changed": what,
            "why_it_matters": "Increases financial risk and debt service burden relative to core operating profitability.",
            "investigate": [
                "refinancing risk and maturity wall",
                "interest rate exposure (fixed vs floating)",
                "covenant headroom",
                "use of proceeds for new debt"
            ]
        }
        
    elif signal_id == "LIQUIDITY_COMPRESSION":
        what = "Cash reserves declined relative to current liabilities."
        curr_cash, curr_cl, prev_cash, prev_cl = get_4(ev)
        if curr_cash is not None and curr_cl is not None and prev_cash is not None and prev_cl is not None and curr_cl != 0 and prev_cl != 0:
            now_ratio = curr_cash / curr_cl
            old_ratio = prev_cash / prev_cl
            what = f"Cash/current-liabilities declined from {old_ratio:.2f}x to {now_ratio:.2f}x."
            
        return {
            "title": "Liquidity Compression",
            "what_changed": what,
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
        curr, prev = get_2(ev)
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
        "title": signal_id.replace("_", " ").title(),
        "what_changed": "Metric triggered predefined deterioration thresholds.",
        "why_it_matters": "Requires standard analyst review to determine drivers of the variation.",
        "investigate": ["review underlying SEC filings and evidence"]
    }
