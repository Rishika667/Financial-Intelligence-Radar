"""
Automated 15-Company Taxonomy Consistency Audit Script.
Analyzes reporting standards, revenue definitions, operating income proxies,
capex classifications, cash flow conventions, and restatements across
all 15 universe companies and 75 reporting periods.
"""

import json
from pathlib import Path
from typing import Dict, Any, List


def run_comparability_audit() -> Dict[str, Any]:
    facts_path = Path("datasets/fundamentals_lens/financial_facts_5yr.json")
    obs_path = Path("datasets/fundamentals_lens/source_observations.json")
    disc_path = Path("datasets/fundamentals_lens/discrepancy_ledger.json")

    with open(facts_path, "r", encoding="utf-8") as f:
        facts = json.load(f)
    with open(obs_path, "r", encoding="utf-8") as f:
        observations = json.load(f)
    with open(disc_path, "r", encoding="utf-8") as f:
        discrepancies = json.load(f)

    companies = sorted(list(set(f["ticker"] for f in facts)))
    audit_results: Dict[str, Any] = {
        "total_companies": len(companies),
        "total_facts": len(facts),
        "total_observations": len(observations),
        "total_discrepancies": len(discrepancies),
        "company_audits": {}
    }

    for ticker in companies:
        c_facts = sorted([f for f in facts if f["ticker"] == ticker], key=lambda x: x["fiscal_year"])
        c_obs = [o for o in observations if o["ticker"] == ticker]
        c_disc = [d for d in discrepancies if d.get("ticker") == ticker]

        # Extract taxonomy details
        rev_defs = sorted(list(set(str(o.get("definition_type")) for o in c_obs if o.get("metric_name") == "revenue")))
        op_defs = sorted(list(set(str(o.get("definition_type")) for o in c_obs if o.get("metric_name") == "operating_income")))
        ni_defs = sorted(list(set(str(o.get("definition_type")) for o in c_obs if o.get("metric_name") == "net_income")))
        ocf_defs = sorted(list(set(str(o.get("definition_type")) for o in c_obs if o.get("metric_name") == "operating_cash_flow")))
        capex_defs = sorted(list(set(str(o.get("definition_type")) for o in c_obs if o.get("metric_name") == "capital_expenditure")))

        # Check statement basis
        stmt_bases = sorted(list(set(f.get("statement_basis") for f in c_facts)))
        currencies = sorted(list(set(f.get("currency") for f in c_facts)))
        units = sorted(list(set(f.get("unit") for f in c_facts)))

        # Specific taxonomy nuance flags
        nuances: List[str] = []
        if ticker == "MARUTI":
            nuances.append("DISC-017: FY25 Total Revenue from Operations (INR 152,000 Cr) vs FY26 Net Sales (INR 174,370 Cr). Like-for-like Net Sales growth is 20.2% vs unadjusted 14.72%.")
        if ticker in ("BAJAJ-AUTO", "BRITANNIA", "DABUR", "HEROMOTOCO", "HINDUNILVR"):
            nuances.append("IND_AS_PBEI_PROXY: Operating income reported as Profit Before Exceptional Items and Tax; includes non-operating other income.")
        if ticker in ("TCS", "INFY", "HCLTECH"):
            nuances.append("IND_AS_EBIT_OPERATING_PROFIT: Operating profit before other income; strictly comparable across Indian IT peers.")
        if ticker == "WMT":
            nuances.append("DISC-016: Total Revenues includes Membership & other income ($648,125M in FY24 vs Net Sales $642,637M).")
        if ticker == "TCS":
            nuances.append("DISC-007: FY24 Legal claim provision of INR 958 Cr classified under exceptional items.")
        if ticker in ("INFY",):
            nuances.append("DISC-004/DISC-009: Restatements and discrete contract provisions documented in ledger.")

        audit_results["company_audits"][ticker] = {
            "name": c_facts[0]["company_name"],
            "country": c_facts[0]["country"],
            "peer_group": c_facts[0]["peer_group_id"],
            "currencies": currencies,
            "units": units,
            "statement_bases": stmt_bases,
            "periods": [f["fiscal_year_label"] for f in c_facts],
            "revenue_definitions": rev_defs,
            "operating_income_definitions": op_defs,
            "net_income_definitions": ni_defs,
            "operating_cash_flow_definitions": ocf_defs,
            "capex_definitions": capex_defs,
            "discrepancies": [d["discrepancy_id"] for d in c_disc],
            "nuances": nuances
        }

    return audit_results


if __name__ == "__main__":
    res = run_comparability_audit()
    print(f"Audited {res['total_companies']} companies across {res['total_facts']} facts.")
    for t, a in res["company_audits"].items():
        print(f"[{t}] {a['name']} ({a['country']}) - Rev: {a['revenue_definitions']}, OpInc: {a['operating_income_definitions']}")
        if a["nuances"]:
            for n in a["nuances"]:
                print(f"   -> Nuance: {n}")
