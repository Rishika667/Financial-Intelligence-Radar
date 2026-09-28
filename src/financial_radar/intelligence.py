
def generate_intelligence(signal_id, company, sector, evidence):
    """
    Translates raw metric changes into structured deterministic analyst intelligence.
    Returns a dict with:
      - title: e.g. "Working-capital deterioration detected"
      - what_changed: explicit description of the metrics
      - investigate: bullet points for analyst investigation
    """
    if signal_id == "RECEIVABLES_REVENUE_DIVERGENCE":
        return {
            "title": "Working-capital deterioration detected",
            "what_changed": "Receivables increased materially faster than revenue, indicating potential collection issues or aggressive revenue recognition.",
            "investigate": [
                "Customer mix and concentration",
                "Changes in payment terms",
                "DSO (Days Sales Outstanding) trends",
                "Contract structure changes"
            ]
        }
    elif signal_id == "INVENTORY_SALES_DIVERGENCE":
        return {
            "title": "Inventory buildup detected",
            "what_changed": "Inventory grew materially faster than sales, suggesting potential overstocking or slowing demand.",
            "investigate": [
                "Product obsolescence risk",
                "Supply chain disruptions vs demand planning",
                "Future discounting/margin pressure",
                "Inventory days outstanding"
            ]
        }
    elif signal_id == "GROSS_MARGIN_COMPRESSION":
        return {
            "title": "Gross Margin Compression",
            "what_changed": "Gross margin declined period-over-period.",
            "investigate": [
                "Input cost inflation (materials, labor, freight)",
                "Pricing power constraints",
                "Product mix shift toward lower-margin segments",
                "Inventory write-downs"
            ]
        }
    elif signal_id == "OPERATING_MARGIN_DETERIORATION":
        return {
            "title": "Operating Deleverage",
            "what_changed": "Operating margin deteriorated despite revenue trends.",
            "investigate": [
                "SG&A expense growth vs revenue growth",
                "R&D spend efficiency",
                "One-time vs recurring structural costs",
                "Fixed cost deleverage"
            ]
        }
    elif signal_id == "EARNINGS_CASH_CONVERSION_DETERIORATION":
        return {
            "title": "Cash Conversion Decline",
            "what_changed": "Operating cash flow declined relative to net income.",
            "investigate": [
                "Non-cash earnings quality",
                "Working capital drag (receivables, inventory)",
                "Capitalized expenses",
                "Timing of cash receipts/disbursements"
            ]
        }
    elif signal_id == "FREE_CASH_FLOW_DETERIORATION":
        return {
            "title": "Free Cash Flow Deterioration",
            "what_changed": "Free cash flow declined materially.",
            "investigate": [
                "Capex cycle vs maintenance capex",
                "Operating cash flow weakness",
                "Dividend/buyback sustainability",
                "Debt service capacity"
            ]
        }
    elif signal_id == "LEVERAGE_INTEREST_BURDEN":
        return {
            "title": "Leverage / Interest Burden Increase",
            "what_changed": "Debt increased relative to operating income.",
            "investigate": [
                "Refinancing risk and maturity wall",
                "Interest rate exposure (fixed vs floating)",
                "Covenant headroom",
                "Use of proceeds for new debt"
            ]
        }
    elif signal_id == "LIQUIDITY_COMPRESSION":
        return {
            "title": "Liquidity Compression",
            "what_changed": "Cash reserves declined relative to current liabilities.",
            "investigate": [
                "Short-term funding needs",
                "Working capital constraints",
                "Revolver capacity",
                "Upcoming near-term maturities"
            ]
        }
    elif signal_id == "SHARE_COUNT_DILUTION":
        return {
            "title": "Share Count Dilution",
            "what_changed": "Diluted share count increased, diluting EPS.",
            "investigate": [
                "Stock-based compensation (SBC) levels",
                "Secondary equity offerings",
                "Convertible debt dilution",
                "Acquisition currency usage"
            ]
        }
    elif signal_id == "MULTI_FACTOR_DETERIORATION_CLUSTER":
        return {
            "title": "Multi-Factor Deterioration Cluster",
            "what_changed": "3 or more fundamental deterioration signals fired simultaneously.",
            "investigate": [
                "Broad fundamental inflection point",
                "Management execution across multiple fronts",
                "Macro/sector headwinds impacting multiple metrics",
                "Review all underlying component signals"
            ]
        }
    return {
        "title": signal_id.replace("_", " ").title(),
        "what_changed": "Metric triggered predefined deterioration thresholds.",
        "investigate": ["Review underlying SEC filings and evidence."]
    }

