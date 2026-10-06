import json
import time
from pathlib import Path
import requests
from datetime import timedelta
from .models import DataQuality, Observation


def derive_standalone_quarter(ytd, prior_ytd):
    required_prior_type = {"YTD_6M": "QUARTER", "YTD_9M": "YTD_6M", "ANNUAL": "YTD_9M"}
    
    cfy = getattr(ytd, "fiscal_year", None)
    cfp = getattr(ytd, "fiscal_period", None)
    pfy = getattr(prior_ytd, "fiscal_year", None)
    pfp = getattr(prior_ytd, "fiscal_period", None)
    
    days = (ytd.period_end - prior_ytd.period_end).days
    
    fiscal_match = False
    if cfy and pfy and cfp and pfp:
        if cfy == pfy:
            if ytd.period_type == "YTD_6M" and cfp == "Q2" and pfp == "Q1":
                fiscal_match = True
            elif ytd.period_type == "YTD_9M" and cfp == "Q3" and pfp == "Q2":
                fiscal_match = True
            elif ytd.period_type == "ANNUAL" and (cfp == "FY" or cfp == "Q4") and pfp == "Q3":
                fiscal_match = True
    elif not cfp or not pfp:
        if cfy and pfy and cfy != pfy:
            fiscal_match = False
        else:
            if 80 <= days <= 105:
                fiscal_match = True

    valid = (
        ytd.value is not None
        and prior_ytd.value is not None
        and ytd.company == prior_ytd.company
        and ytd.metric == prior_ytd.metric
        and ytd.unit == prior_ytd.unit
        and required_prior_type.get(ytd.period_type) == prior_ytd.period_type
        and fiscal_match
        and ytd.comparable
        and prior_ytd.comparable
    )

    if not valid:
        return Observation(
            company=ytd.company,
            metric=ytd.metric,
            value=None,
            unit=ytd.unit,
            period_end=ytd.period_end,
            period_type="QUARTER",
            quality=DataQuality.CALCULATION_INVALID,
            comparable=False,
            comparability_reason="Invalid derivation inputs",
            provenance=tuple(),
        )

    fp = None
    if ytd.period_type == "YTD_6M": fp = "Q2"
    elif ytd.period_type == "YTD_9M": fp = "Q3"
    elif ytd.period_type == "ANNUAL": fp = "Q4"
    
    return Observation(
        company=ytd.company, 
        metric=ytd.metric, 
        value=ytd.value - prior_ytd.value, 
        unit=ytd.unit,
        period_end=ytd.period_end, 
        period_type="QUARTER", 
        quality=DataQuality.DERIVED,
        provenance=ytd.provenance + prior_ytd.provenance,
        derived_from=(f"{ytd.metric} {ytd.period_end.isoformat()} {ytd.period_type}", f"{prior_ytd.metric} {prior_ytd.period_end.isoformat()} {prior_ytd.period_type}"),
        period_start=prior_ytd.period_end + timedelta(days=1),
        fiscal_year=ytd.fiscal_year,
        fiscal_period=fp
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

    def submissions(self, cik, fetch_historical=False):
        payload = self.get_json(f"https://data.sec.gov/submissions/CIK{int(cik):010d}.json", f"submissions/CIK{int(cik):010d}.json")
        if fetch_historical:
            recent = payload.get("filings", {}).get("recent", {})
            for f in payload.get("filings", {}).get("files", []):
                if name := f.get("name"):
                    hist = self.get_json(f"https://data.sec.gov/submissions/{name}", f"submissions/{name}")
                    for k in recent:
                        if k in hist:
                            recent[k].extend(hist[k])
        return payload
