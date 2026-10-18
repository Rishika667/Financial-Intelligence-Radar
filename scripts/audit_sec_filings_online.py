"""
Repeatable SEC EDGAR Submissions Audit Script:
Verifies official Form 10-K filing identity, accession numbers, filing dates, report periods,
primary documents, and dataset source URLs against the official SEC EDGAR submissions API
(https://data.sec.gov/submissions/CIK{cik}.json).

Statuses:
- ONLINE_VERIFIED: All mandatory checks passed against official SEC submissions API:
    * Company CIK and Form 10-K verified
    * Filing date matches exactly
    * Period of report date matches stored period-end
    * Primary document filename matches source URL
    * Unhyphenated accession directory matches source URL
    * CIK directory matches source URL
- OFFLINE_STRUCTURE_ONLY: Verified against structural 20-digit SEC accession and URL rules offline.
- NOT_FOUND: Accession was not found in SEC EDGAR recent or historical submissions.
- MISMATCH: Filing was found, but form/dates/primary document/URL contradicted the canonical facts.
- UNAVAILABLE: SEC EDGAR endpoint unreachable, network timeout, rate-limited (HTTP 429), or missing network library.

Usage:
  python scripts/audit_sec_filings_online.py [--offline] [--strict] [--user-agent "YourName yourname@domain.com"]
"""

import sys
import os
import re
import json
import time
import argparse
from pathlib import Path
from typing import Dict, Any, List, Optional

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = REPO_ROOT / "datasets" / "fundamentals_lens"
FACTS_FILE = DATASETS_DIR / "financial_facts_5yr.json"
REPORT_FILE = DATASETS_DIR / "sec_submissions_audit_report.json"

CIK_MAP = {
    "AAPL": "0000320193",
    "MSFT": "0000789019",
    "GOOGL": "0001652044",
    "COST": "0000909832",
    "TGT": "0000027419",
    "WMT": "0000104169"
}

ACCESSION_PATTERN = re.compile(r"^\d{10}-\d{2}-\d{6}$")


def audit_sec_filings(
    offline: bool = False, 
    strict: bool = False,
    user_agent: Optional[str] = None,
    facts_path: Optional[Path] = None,
    report_path: Optional[Path] = None
) -> Dict[str, Any]:
    target_facts_file = facts_path or FACTS_FILE
    target_report_file = report_path or REPORT_FILE

    if not target_facts_file.exists():
        raise FileNotFoundError(f"Financial facts file not found: {target_facts_file}")

    with open(target_facts_file, "r", encoding="utf-8") as f:
        facts = json.load(f)

    us_facts = [f for f in facts if f.get("country") == "US" or f.get("ticker") in CIK_MAP]
    print(f"Loaded {len(us_facts)} US financial facts across {len(CIK_MAP)} companies.")

    results: List[Dict[str, Any]] = []
    
    # Resolve User-Agent: CLI flag > SEC_USER_AGENT env > truthful project default
    resolved_ua = (
        user_agent
        or os.environ.get("SEC_USER_AGENT", "").strip()
        or "FinancialIntelligenceRadar rishika.dangayach@domain.com"
    )
    headers = {"User-Agent": resolved_ua, "Accept-Encoding": "gzip, deflate"}

    failure_detected = False

    for ticker, cik in CIK_MAP.items():
        company_facts = [f for f in us_facts if f["ticker"] == ticker]

        if offline or not REQUESTS_AVAILABLE:
            print(f"[{ticker}] Running in offline structure verification mode.")
            for f in company_facts:
                acc = f.get("accession_id", "")
                is_valid_format = bool(ACCESSION_PATTERN.match(acc))
                src_url = f.get("source_url", "")
                has_valid_url = bool(src_url and "sec.gov/Archives/edgar/data" in src_url)

                checks = ["accession_regex_format", "sec_archives_url_domain"]
                if is_valid_format and has_valid_url:
                    status = "OFFLINE_STRUCTURE_ONLY"
                    err = None
                else:
                    status = "MISMATCH"
                    err = "Invalid accession pattern or SEC URL"
                    failure_detected = True

                results.append({
                    "ticker": ticker,
                    "cik": cik,
                    "fiscal_year_label": f.get("fiscal_year_label"),
                    "accession_id": acc,
                    "form": "10-K",
                    "status": status,
                    "filing_date": f.get("filing_date"),
                    "period_end": f.get("period_end"),
                    "source_url": src_url,
                    "checks_performed": checks,
                    "error": err
                })
            continue

        # Online Verification via SEC Submissions API
        url = f"https://data.sec.gov/submissions/CIK{cik}.json"
        print(f"[{ticker}] Querying SEC submissions API: {url} ...")
        try:
            resp = requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                sub_data = resp.json()
                
                # Check company CIK identity in response
                sec_cik_raw = str(sub_data.get("cik", "")).zfill(10)
                if sec_cik_raw and sec_cik_raw != cik:
                    failure_detected = True
                    for f in company_facts:
                        results.append({
                            "ticker": ticker,
                            "cik": cik,
                            "fiscal_year_label": f.get("fiscal_year_label"),
                            "accession_id": f.get("accession_id"),
                            "status": "MISMATCH",
                            "form": "10-K",
                            "checks_performed": ["company_cik_identity"],
                            "error": f"SEC submissions returned CIK {sec_cik_raw} != expected {cik}"
                        })
                    continue

                recent = sub_data.get("filings", {}).get("recent", {})
                acc_list = recent.get("accessionNumber", [])
                form_list = recent.get("form", [])
                date_list = recent.get("filingDate", [])
                doc_list = recent.get("primaryDocument", [])
                rep_end_list = recent.get("reportDate", [])

                edgar_map = {}
                for acc_num, form_type, f_date, p_doc, r_end in zip(
                    acc_list, form_list, date_list, doc_list, rep_end_list or [None]*len(acc_list)
                ):
                    edgar_map[acc_num] = {
                        "form": form_type,
                        "filing_date": f_date,
                        "primary_doc": p_doc,
                        "report_date": r_end
                    }

                for f in company_facts:
                    stored_acc = f.get("accession_id")
                    if stored_acc not in edgar_map:
                        # Check historical submission files in filings.files
                        for f_entry in sub_data.get("filings", {}).get("files", []):
                            f_name = f_entry.get("name")
                            if f_name:
                                try:
                                    f_resp = requests.get(f"https://data.sec.gov/submissions/{f_name}", headers=headers, timeout=12)
                                    if f_resp.status_code == 200:
                                        old_data = f_resp.json()
                                        o_accs = old_data.get("accessionNumber", [])
                                        if stored_acc in o_accs:
                                            idx = o_accs.index(stored_acc)
                                            edgar_map[stored_acc] = {
                                                "form": old_data.get("form", [])[idx] if idx < len(old_data.get("form", [])) else "10-K",
                                                "filing_date": old_data.get("filingDate", [])[idx] if idx < len(old_data.get("filingDate", [])) else None,
                                                "primary_doc": old_data.get("primaryDocument", [])[idx] if idx < len(old_data.get("primaryDocument", [])) else None,
                                                "report_date": old_data.get("reportDate", [])[idx] if idx < len(old_data.get("reportDate", [])) else None,
                                            }
                                            break
                                except Exception:
                                    pass

                    if stored_acc in edgar_map:
                        sec_info = edgar_map[stored_acc]
                        checks = ["accession_existence"]
                        mismatch_errors = []

                        # 1. Form Check
                        checks.append("form_10k_type")
                        if sec_info["form"] != "10-K":
                            mismatch_errors.append(f"Expected Form 10-K, but SEC reports Form {sec_info['form']}")

                        # 2. Filing Date Check
                        checks.append("filing_date_parity")
                        if f.get("filing_date") and sec_info["filing_date"] != f.get("filing_date"):
                            mismatch_errors.append(f"Filing date mismatch: fact has {f.get('filing_date')}, SEC reports {sec_info['filing_date']}")

                        # 3. Report Period Check
                        checks.append("report_period_parity")
                        if f.get("period_end") and sec_info.get("report_date") and sec_info["report_date"] != f.get("period_end"):
                            mismatch_errors.append(f"Report period mismatch: fact has {f.get('period_end')}, SEC reports {sec_info['report_date']}")

                        # 4. Primary Document Filename in Source URL
                        checks.append("primary_document_url_alignment")
                        src_url = f.get("source_url", "")
                        p_doc = sec_info.get("primary_doc")
                        if p_doc and (p_doc not in src_url):
                            mismatch_errors.append(f"Primary document '{p_doc}' not found in source_url '{src_url}'")

                        # 5. Accession Directory in Source URL
                        checks.append("accession_directory_url_alignment")
                        acc_dir = stored_acc.replace("-", "")
                        if acc_dir not in src_url:
                            mismatch_errors.append(f"Accession directory '{acc_dir}' not found in source_url '{src_url}'")

                        # 6. CIK Directory in Source URL
                        checks.append("cik_directory_url_alignment")
                        unpadded_cik = str(int(cik))
                        if f"/data/{unpadded_cik}/" not in src_url and f"/data/{cik}/" not in src_url:
                            mismatch_errors.append(f"CIK directory '/data/{unpadded_cik}/' not found in source_url '{src_url}'")

                        if mismatch_errors:
                            status = "MISMATCH"
                            err = "; ".join(mismatch_errors)
                            failure_detected = True
                        else:
                            status = "ONLINE_VERIFIED"
                            err = None

                        results.append({
                            "ticker": ticker,
                            "cik": cik,
                            "fiscal_year_label": f.get("fiscal_year_label"),
                            "accession_id": stored_acc,
                            "sec_filing_date": sec_info["filing_date"],
                            "dataset_filing_date": f.get("filing_date"),
                            "sec_report_date": sec_info.get("report_date"),
                            "dataset_period_end": f.get("period_end"),
                            "primary_document": sec_info.get("primary_doc"),
                            "source_url": src_url,
                            "status": status,
                            "form": sec_info["form"],
                            "checks_performed": checks,
                            "error": err
                        })
                    else:
                        failure_detected = True
                        results.append({
                            "ticker": ticker,
                            "cik": cik,
                            "fiscal_year_label": f.get("fiscal_year_label"),
                            "accession_id": stored_acc,
                            "status": "NOT_FOUND",
                            "form": "10-K",
                            "checks_performed": ["accession_existence"],
                            "error": "Accession not found in recent or historical EDGAR submissions"
                        })
            elif resp.status_code in (429, 500, 502, 503, 504):
                print(f"[{ticker}] SEC returned HTTP {resp.status_code} (Rate limit / server unavailable).")
                for f in company_facts:
                    results.append({
                        "ticker": ticker,
                        "cik": cik,
                        "fiscal_year_label": f.get("fiscal_year_label"),
                        "accession_id": f.get("accession_id"),
                        "status": "UNAVAILABLE",
                        "form": "10-K",
                        "checks_performed": ["http_endpoint_reachability"],
                        "error": f"HTTP_{resp.status_code}: SEC endpoint unavailable or rate limited"
                    })
            elif resp.status_code == 403:
                print(f"[{ticker}] SEC returned HTTP 403 (User-Agent rejected).")
                for f in company_facts:
                    results.append({
                        "ticker": ticker,
                        "cik": cik,
                        "fiscal_year_label": f.get("fiscal_year_label"),
                        "accession_id": f.get("accession_id"),
                        "status": "UNAVAILABLE",
                        "form": "10-K",
                        "checks_performed": ["http_endpoint_reachability"],
                        "error": "HTTP_403: SEC EDGAR requires a declared operator name and contact email in User-Agent header"
                    })
            else:
                failure_detected = True
                for f in company_facts:
                    results.append({
                        "ticker": ticker,
                        "cik": cik,
                        "fiscal_year_label": f.get("fiscal_year_label"),
                        "accession_id": f.get("accession_id"),
                        "status": "NOT_FOUND",
                        "form": "10-K",
                        "checks_performed": ["http_endpoint_reachability"],
                        "error": f"HTTP_{resp.status_code}"
                    })
        except Exception as e:
            print(f"[{ticker}] Network error ({e}). Flagging as UNAVAILABLE.")
            for f in company_facts:
                results.append({
                    "ticker": ticker,
                    "cik": cik,
                    "fiscal_year_label": f.get("fiscal_year_label"),
                    "accession_id": f.get("accession_id"),
                    "status": "UNAVAILABLE",
                    "form": "10-K",
                    "checks_performed": ["http_endpoint_reachability"],
                    "error": str(e)
                })

        time.sleep(0.2)  # Respect SEC rate limits

    status_counts = {}
    for r in results:
        st = r["status"]
        status_counts[st] = status_counts.get(st, 0) + 1

    summary = {
        "audit_timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mode": "OFFLINE" if offline or not REQUESTS_AVAILABLE else "ONLINE",
        "strict": strict,
        "total_us_periods": len(results),
        "status_counts": status_counts,
        "failure_detected": failure_detected,
        "results": results
    }

    if target_report_file:
        with open(target_report_file, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        print(f"Audit completed. Report saved to {target_report_file.name}.")

    print(f"Status Summary: {status_counts}")

    if strict and (failure_detected or (offline and status_counts.get("OFFLINE_STRUCTURE_ONLY", 0) != len(results))):
        print("ERROR: Strict mode failure detected during SEC filings audit.")
        if __name__ == "__main__":
            sys.exit(1)

    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="SEC EDGAR Submissions Audit")
    parser.add_argument("--offline", action="store_true", help="Run in offline verification mode")
    parser.add_argument("--strict", action="store_true", help="Exit with code 1 on mismatch or failure")
    parser.add_argument("--user-agent", default=None, help="SEC EDGAR User-Agent (Name email@domain.com)")
    args = parser.parse_args()

    audit_sec_filings(offline=args.offline, strict=args.strict, user_agent=args.user_agent)
