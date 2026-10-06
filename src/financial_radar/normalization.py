from datetime import date, datetime
from collections import defaultdict
from .models import Observation, Provenance, DataQuality
from .core import derive_standalone_quarter
import logging

logger = logging.getLogger(__name__)

CONCEPTS = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"),
    "gross_profit": ("GrossProfit",),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss",),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capital_expenditures": ("PaymentsToAcquirePropertyPlantAndEquipment",),
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
                    # Do not treat dimensional facts as consolidated totals
                    if "segment" in x or "axis" in x or "member" in x:
                        continue

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
                    start_dt = None

                    fy = x.get("fy")
                    fp = x.get("fp")
                    
                    if not start_str:
                        pt = "INSTANT"
                    else:
                        try:
                            start_dt = date.fromisoformat(start_str)
                            days = (end_dt - start_dt).days
                            
                            if fp == "FY" or (350 <= days <= 380):
                                pt = "ANNUAL"
                            elif fp == "Q1":
                                pt = "QUARTER"
                            elif fp == "Q2":
                                pt = "YTD_6M" if days > 120 else "QUARTER"
                            elif fp == "Q3":
                                pt = "YTD_9M" if days > 200 else "QUARTER"
                            elif fp == "Q4":
                                pt = "QUARTER"
                            elif fp == "H1":
                                pt = "YTD_6M"
                            else:
                                # secondary guard
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
                        x.get("form", ""), tag, datetime.utcnow(), val, "v1",
                        start_dt,
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
                        "tag_idx": tag_idx,
                        "start": start_dt,
                        "fy": fy,
                        "fp": fp,
                    })

    # 2. Canonical Fact Selection (deduplication, restatements, amendments)
    #    Key includes unit and start to prevent collapsing incompatible facts.
    canonical = {}
    for f in raw_facts:
        key = (f["metric"], f["end"], f["pt"], f["unit"], f.get("start"))
        if key not in canonical:
            canonical[key] = f
        else:
            curr = canonical[key]
            # Priority: lower tag_idx (standard concept preferred)
            if f["tag_idx"] < curr["tag_idx"]:
                f["provenance"] = f.get("provenance", (f["prov"],)) + curr.get("provenance", (curr["prov"],))
                canonical[key] = f
            elif f["tag_idx"] == curr["tag_idx"]:
                # Same tag: prefer later filing (handles restatements)
                if f["filed"] > curr["filed"] or (f["filed"] == curr["filed"] and f["quality"] == DataQuality.AMENDED):
                    f["provenance"] = f.get("provenance", (f["prov"],)) + curr.get("provenance", (curr["prov"],))
                    canonical[key] = f

    # 3. Debt Aggregation (Current + Noncurrent ONLY if no valid total-debt fact exists)
    #    Keys are 5-tuples: (metric, end, pt, unit, start).
    #    Instant facts have start=None.
    instant_ends = {(k[1], k[3]) for k in canonical.keys() if k[2] == "INSTANT"}
    for end, unit in instant_ends:
        # Check whether a valid total-debt fact already exists
        has_total_debt = any(
            k[0] == "debt" and k[1] == end and k[2] == "INSTANT" and k[3] == unit
            for k in canonical
        )
        if not has_total_debt:
            c_debt = canonical.get(("debt_current", end, "INSTANT", unit, None))
            nc_debt = canonical.get(("debt_noncurrent", end, "INSTANT", unit, None))
            if c_debt and nc_debt and c_debt["value"] is not None and nc_debt["value"] is not None:
                canonical[("debt", end, "INSTANT", unit, None)] = {
                    "metric": "debt",
                    "value": c_debt["value"] + nc_debt["value"],
                    "unit": unit,
                    "end": end,
                    "pt": "INSTANT",
                    "quality": DataQuality.DERIVED,
                    "provenance": c_debt.get("provenance", (c_debt["prov"],)) + nc_debt.get("provenance", (nc_debt["prov"],)),
                    "filed": max(c_debt["filed"], nc_debt["filed"]),
                    "tag_idx": 0,
                    "derived_from": (f"debt_current {end.isoformat()} INSTANT", f"debt_noncurrent {end.isoformat()} INSTANT"),
                    "start": None,
                    "fy": c_debt.get("fy"),
                    "fp": c_debt.get("fp"),
                }

    obs_map = defaultdict(list)
    out = []
    found_metrics = set()

    for key, f in canonical.items():
        metric = f["metric"]
        if metric in ("debt_current", "debt_noncurrent"):
            continue

        found_metrics.add(metric)
        provs = f.get("provenance")
        if provs is None:
            provs = (f["prov"],)
        o = Observation(
            company, metric, f["value"], f["unit"], f["end"], f["pt"],
            f["quality"], provs, f.get("derived_from", ()),
            True, None, f.get("start"),
            f.get("fy"), f.get("fp")
        )
        obs_map[metric].append(o)
        out.append(o)

    # 4. Fill missing standard metrics
    for metric in CONCEPTS.keys():
        if metric not in found_metrics and metric not in ("debt_current", "debt_noncurrent"):
            out.append(Observation(
                company, metric, None, "USD", date.today(), "UNKNOWN",
                DataQuality.NOT_REPORTED, comparable=False,
                comparability_reason="No accepted standard XBRL concept",
            ))

# 5. Derive Standalone Quarters from YTD
    def find_ytd(obs_list, o, req_type):
        candidates = []
        for c in obs_list:
            if c.period_type != req_type or c.unit != o.unit:
                continue
            cfy = getattr(o, "fiscal_year", None)
            cfp = getattr(o, "fiscal_period", None)
            pfy = getattr(c, "fiscal_year", None)
            pfp = getattr(c, "fiscal_period", None)
            
            is_match = False
            if cfy and pfy and cfp and pfp:
                if cfy == pfy:
                    if req_type == "QUARTER" and cfp in ("Q2", "H1") and pfp == "Q1": is_match = True
                    if req_type == "YTD_6M" and cfp == "Q3" and pfp in ("Q2", "H1"): is_match = True
                    if req_type == "YTD_9M" and cfp == "FY" and pfp == "Q3": is_match = True
            elif 80 <= (o.period_end - c.period_end).days <= 100:
                is_match = True
                
            if is_match:
                candidates.append(c)
                
        if not candidates:
            return None
            
        from .models import QUALITY_RANK
        candidates.sort(key=lambda x: (
            QUALITY_RANK.get(getattr(x, "quality", None), 0),
            x.period_end,
            getattr(x, "period_start", None) or date.min
        ), reverse=True)
        return candidates[0]

    for metric, obs_list in obs_map.items():
        for o in obs_list:
            if o.period_type == "YTD_6M":
                q1 = find_ytd(obs_list, o, "QUARTER")
                if q1:
                    derived = derive_standalone_quarter(o, q1)
                    if derived.value is not None:
                        out.append(derived)
            elif o.period_type == "YTD_9M":
                ytd6 = find_ytd(obs_list, o, "YTD_6M")
                if ytd6:
                    derived = derive_standalone_quarter(o, ytd6)
                    if derived.value is not None:
                        out.append(derived)
            elif o.period_type == "ANNUAL":
                ytd9 = find_ytd(obs_list, o, "YTD_9M")
                if ytd9:
                    derived = derive_standalone_quarter(o, ytd9)
                    if derived.value is not None:
                        out.append(derived)

    return out
