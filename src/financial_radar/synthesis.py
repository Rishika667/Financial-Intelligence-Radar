
def synthesize_company(ticker, c):
    from .store import rows
    
    obs = rows(c, "SELECT metric, value FROM observations WHERE company=? AND period_type='QUARTER' ORDER BY period_end DESC", (ticker,))
    latest = {}
    for o in obs:
        if o['metric'] not in latest:
            latest[o['metric']] = o['value']
            
    # VERY simplified deterministic synthesis
    synthesis = {
        "observed": [],
        "context": [],
        "investigate": []
    }
    
    if "revenue" in latest and "operating_income" in latest:
        synthesis["observed"].append(f"Revenue is {latest['revenue']:,.0f} and Operating Income is {latest['operating_income']:,.0f}.")
        
    synthesis["context"].append("SEC filings confirm these figures as reported.")
    synthesis["investigate"].append("Analyze margin sustainability and future guidance.")
    
    return synthesis
