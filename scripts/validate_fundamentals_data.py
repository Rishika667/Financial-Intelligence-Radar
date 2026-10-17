#!/usr/bin/env python3
"""
CLI Script to validate the Fundamentals Lens canonical dataset.
Runs all validation gates and outputs a comprehensive integrity report.
"""

import sys
from pathlib import Path

# Add src to sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "src"))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from fundamentals_lens.data_loader import (
    load_companies,
    load_financial_facts,
    load_source_register,
    load_coverage_report,
    get_facts_for_company
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.models import ValidationStatus


def run_validation():
    print("=" * 80)
    print("FUNDAMENTALS LENS: FINANCIAL DATA INTEGRITY VALIDATION")
    print("=" * 80)
    
    companies = load_companies()
    all_facts = load_financial_facts()
    sources = load_source_register()
    coverage = load_coverage_report()
    
    print(f"Total Companies Loaded:  {len(companies)}")
    print(f"Total Financial Records: {len(all_facts)}")
    print(f"Total Sources Listed:    {len(sources)}")
    print(f"Coverage Reports:        {len(coverage)}")
    print("-" * 80)
    
    total_checks = 0
    passed_checks = 0
    failed_checks = 0
    unverified_checks = 0
    
    company_pass_map = {}
    
    for comp in sorted(companies, key=lambda c: (c.peer_group_id, c.ticker)):
        facts = get_facts_for_company(comp.ticker)
        results = FundamentalsValidator.validate_company_dataset(comp, facts, sources, coverage=coverage)
        
        company_passed = True
        print(f"\n[{comp.ticker}] {comp.name} ({comp.peer_group_name}) — {len(facts)} periods")
        
        for r in results:
            total_checks += 1
            status_icon = "PASS" if r.status == ValidationStatus.PASS else "FAIL"
            if r.status == ValidationStatus.FAIL:
                status_icon = "FAIL"
                failed_checks += 1
                company_passed = False
            elif r.status == ValidationStatus.UNVERIFIED:
                status_icon = "UNVERIFIED"
                unverified_checks += 1
                company_passed = False
            else:
                passed_checks += 1
                
            print(f"  [{status_icon:10}] {r.rule_name}: {r.message}")
            if r.details.get("warnings"):
                for w in r.details["warnings"]:
                    print(f"               * REVIEW FLAG: {w}")
                    
        company_pass_map[comp.ticker] = company_passed

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)
    print(f"Total Checks Executed:    {total_checks}")
    print(f"Total Passed:             {passed_checks}")
    print(f"Total Failed:             {failed_checks}")
    print(f"Total Unverified:         {unverified_checks}")
    print(f"Companies Passing 100%:   {sum(company_pass_map.values())} / {len(companies)}")
    print("=" * 80)
    
    if failed_checks > 0 or unverified_checks > 0:
        print("RESULT: VALIDATION GATES FAILED")
        return 1
    else:
        print("RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)")
        return 0


if __name__ == "__main__":
    sys.exit(run_validation())
