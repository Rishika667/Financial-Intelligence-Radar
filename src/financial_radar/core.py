import json
import time
from pathlib import Path
import requests
from datetime import timedelta
from .models import DataQuality, Observation

def pct_change(current, prior):
    return None if current is None or prior is None or prior == 0 else (current - prior) / abs(prior)

def derive_standalone_quarter(ytd, prior_ytd):
    required_prior_type = {"YTD_6M": "QUARTER", "YTD_9M": "YTD_6M", "ANNUAL": "YTD_9M"}
    valid = (
        ytd.value is not None
        and prior_ytd.value is not None
        and ytd.company == prior_ytd.company
        and ytd.metric == prior_ytd.metric
        and ytd.unit == prior_ytd.unit
        and required_prior_type.get(ytd.period_type) == prior_ytd.period_type
        and 80 <= (ytd.period_end - prior_ytd.period_end).days <= 100
        and ytd.comparable
        and prior_ytd.comparable
    )
    if not valid:
        return Observation(
            ytd.company, ytd.metric, None, ytd.unit, ytd.period_end, "QUARTER",
            DataQuality.CALCULATION_INVALID, comparable=False,
            comparability_reason="Invalid YTD contexts"
        )
    return Observation(
        ytd.company, ytd.metric, ytd.value - prior_ytd.value, ytd.unit,
        ytd.period_end, "QUARTER", DataQuality.DERIVED,
        ytd.provenance + prior_ytd.provenance,
        derived_from=(f"{ytd.metric} {ytd.period_end.isoformat()} {ytd.period_type}", f"{prior_ytd.metric} {prior_ytd.period_end.isoformat()} {prior_ytd.period_type}"),
        period_start=prior_ytd.period_end + timedelta(days=1)
    )

def free_cash_flow(ocf, capex):
    valid = (
        ocf.value is not None 
        and capex.value is not None 
        and ocf.comparable 
        and capex.comparable
        and ocf.company == capex.company
        and ocf.unit == capex.unit
        and ocf.period_end == capex.period_end
        and ocf.period_type == capex.period_type
    )
    if not valid:
        return Observation(
            ocf.company, "free_cash_flow", None, ocf.unit, ocf.period_end,
            ocf.period_type, DataQuality.CALCULATION_INVALID, comparable=False
        )
    return Observation(
        ocf.company, "free_cash_flow", ocf.value - abs(capex.value), ocf.unit,
        ocf.period_end, ocf.period_type, DataQuality.DERIVED,
        ocf.provenance + capex.provenance,
        derived_from=(f"operating_cash_flow {ocf.period_end.isoformat()} {ocf.period_type}", f"capex {capex.period_end.isoformat()} {capex.period_type}"),
        period_start=ocf.period_start
    )

class SECClient:
    def __init__(self, user_agent, raw_dir="data/raw", min_interval_seconds=0.2):
        if not user_agent or "@" not in user_agent:
            raise ValueError("SEC User-Agent must identify operator and contact email")
        self.s = requests.Session()
        self.s.headers.update({"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"})
        self.raw = Path(raw_dir)
        self.delay = min_interval_seconds
        self.last = 0

    def get_json(self, url, key):
        pause = self.delay - (time.monotonic() - self.last)
        if pause > 0:
            time.sleep(pause)
        r = self.s.get(url, timeout=30)
        self.last = time.monotonic()
        r.raise_for_status()
        payload = r.json()
        target = self.raw / key
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return payload

    def company_facts(self, cik):
        return self.get_json(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json", f"companyfacts/CIK{int(cik):010d}.json")

    def submissions(self, cik):
        return self.get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", f"submissions/CIK{int(cik):010d}.json")
