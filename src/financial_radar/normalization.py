from datetime import date, datetime
from collections import defaultdict
from .models import Observation, Provenance, DataQuality
from .core import derive_standalone_quarter

CONCEPTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
    "accounts_receivable": ("AccountsReceivableNetCurrent",),
    "inventory": ("InventoryNet",),
    "cash_and_equivalents": ("CashAndCashEquivalentsAtCarryingValue",),
    "current_liabilities": ("LiabilitiesCurrent",),
    "debt": ("DebtInstrumentCarryingAmount", "LongTermDebt", "LongTermDebtAndCapitalLeaseObligations"),
    "debt_current": ("LongTermDebtCurrent", "DebtCurrent"),
    "debt_noncurrent": ("LongTermDebtNoncurrent",),
    "share_count": ("WeightedAverageNumberOfDilutedSharesOutstanding",)
}

def extract_companyfacts(company, cik, payload, filings):
    raw_facts = []
    
    # 1. Gather all candidate facts
    for metric, tags in CONCEPTS.items():
        for tag_idx, tag in enumerate(tags):
            for unit, items in payload.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).items():
                for x in items:
                    acc = x.get("accn", "").replace("-", "")
                    filing = filings.get(acc, {})
                    if not filing:
                        continue
                    
                    try:
                        end_dt = date.fromisoformat(x["end"])
                        filed_dt = date.fromisoformat(x["filed"])
                        val = float(x.get("val")) if x.get("val") is not None else None
                    except (ValueError, TypeError):
                        continue
                        
                    start_str = x.get("start")
                    
                    if not start_str:
                        pt = "INSTANT"
                    else:
                        try:
                            start_dt = date.fromisoformat(start_str)
                            days = (end_dt - start_dt).days
                            if 80 <= days <= 100:
                                pt = "QUARTER"
                            elif 170 <= days <= 190:
                                pt = "YTD_6M"
                            elif 260 <= days <= 280:
                                pt = "YTD_9M"
                            elif 350 <= days <= 380:
                                pt = "ANNUAL"
                            else:
                                pt = "UNKNOWN"
                        except ValueError:
                            pt = "UNKNOWN"
                            
                    q = DataQuality.AMENDED if str(x.get("form", "")).endswith("/A") else DataQuality.REPORTED
                    prov = Provenance(
                        acc, filing.get("source_url", ""), filed_dt,
                        x.get("form", ""), tag, datetime.utcnow(), val
                    )
                    
                    raw_facts.append({
                        "metric": metric,
                        "value": val,
                        "unit": unit,
                        "end": end_dt,
                        "pt": pt,
                        "quality": q,
                        "prov": prov,
                        "filed": filed_dt,
                        "tag_idx": tag_idx
                    })

    # 2. Canonical Fact Selection (deduplication, restatements, amendments)
    canonical = {}
    for f in raw_facts:
        key = (f["metric"], f["end"], f["pt"])
        if key not in canonical:
            canonical[key] = f
        else:
            curr = canonical[key]
            # Priority: lower tag_idx (closer to index 0)
            if f["tag_idx"] < curr["tag_idx"]:
                canonical[key] = f
            elif f["tag_idx"] == curr["tag_idx"]:
                # If same tag, prefer newer filing
                if f["filed"] > curr["filed"]:
                    canonical[key] = f
                elif f["filed"] == curr["filed"] and f["quality"] == DataQuality.AMENDED:
                    canonical[key] = f

    # 3. Debt Aggregation (Current + Noncurrent if Total is missing)
    instants = { (k[1], k[2]): [] for k in canonical.keys() if k[2] == "INSTANT" }
    for k in instants.keys():
        end, pt = k
        if ("debt", end, pt) not in canonical:
            c_debt = canonical.get(("debt_current", end, pt))
            nc_debt = canonical.get(("debt_noncurrent", end, pt))
            if c_debt and nc_debt and c_debt["value"] is not None and nc_debt["value"] is not None:
                canonical[("debt", end, pt)] = {
                    "metric": "debt",
                    "value": c_debt["value"] + nc_debt["value"],
                    "unit": c_debt["unit"],
                    "end": end,
                    "pt": pt,
                    "quality": DataQuality.DERIVED,
                    "prov_tuple": (c_debt["prov"], nc_debt["prov"]),
                    "filed": max(c_debt["filed"], nc_debt["filed"]),
                    "tag_idx": 0
                }

    obs_map = defaultdict(list)
    out = []
    found_metrics = set()
    
    for key, f in canonical.items():
        metric = f["metric"]
        if metric in ("debt_current", "debt_noncurrent"):
            continue
            
        found_metrics.add(metric)
        provs = f.get("prov_tuple", (f["prov"],))
        o = Observation(company, metric, f["value"], f["unit"], f["end"], f["pt"], f["quality"], provs)
        obs_map[metric].append(o)
        out.append(o)

    # 4. Fill missing standard metrics
    for metric in CONCEPTS.keys():
        if metric not in found_metrics and metric not in ("debt_current", "debt_noncurrent"):
            out.append(Observation(
                company, metric, None, "USD", date.today(), "UNKNOWN",
                DataQuality.NOT_REPORTED, comparable=False,
                comparability_reason="No accepted standard XBRL concept"
            ))

    # 5. Derive Standalone Quarters from YTD
    for metric, obs_list in obs_map.items():
        for o in obs_list:
            if o.period_type == "YTD_6M":
                # Find Q1 (QUARTER) ending ~3 months prior
                q1 = next((c for c in obs_list if c.period_type == "QUARTER" and 80 <= (o.period_end - c.period_end).days <= 100), None)
                if q1:
                    out.append(derive_standalone_quarter(o, q1))
            elif o.period_type == "YTD_9M":
                # Find YTD_6M ending ~3 months prior
                ytd6 = next((c for c in obs_list if c.period_type == "YTD_6M" and 80 <= (o.period_end - c.period_end).days <= 100), None)
                if ytd6:
                    out.append(derive_standalone_quarter(o, ytd6))

    return out
