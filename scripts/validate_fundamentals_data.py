#!/usr/bin/env python3
"""
CLI Script to validate the Fundamentals Lens canonical dataset.
Runs all validation gates and outputs a comprehensive multi-dimensional integrity report (Phase 6 Hardened).
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
    load_evidence_register,
    load_discrepancy_ledger,
    get_facts_for_company
)
from fundamentals_lens.validator import FundamentalsValidator
from fundamentals_lens.models import ValidationStatus


def run_validation():
    print("=" * 80)
    print("FUNDAMENTALS LENS: FINANCIAL DATA INTEGRITY VALIDATION (PHASE 8)")
    print("=" * 80)
    
    companies = load_companies()
    all_facts = load_financial_facts()
    sources = load_source_register()
    coverage = load_coverage_report()
    evidence_register = load_evidence_register()
    discrepancies = load_discrepancy_ledger()
    
    counts = FundamentalsValidator.get_metric_verification_counts(evidence_register)
    
    print(f"Total Companies Loaded:      {len(companies)}")
    print(f"Total Financial Periods:     {len(all_facts)}")
    print(f"Total Sources Listed:        {len(sources)}")
    print(f"Coverage Reports:            {len(coverage)}")
    print(f"Evidence Register Records:   {len(evidence_register)}")
    print(f"Total Primary Metrics:       {counts['total_primary_metrics']}")
    print(f"Independently Reconciled:    {counts['independently_reconciled']} primary metrics")
    print(f"Source-Linked Only:          {counts['source_linked_only']} primary metrics")
    print(f"Unverified / Discrepant:     {counts['unverified']} primary metrics")
    print(f"Derived Free Cash Flow:      {counts['fcf_derived']} periods (DERIVED_VERIFIED)")
    print("-" * 80)
    
    total_checks = 0
    passed_checks = 0
    warning_checks = 0
    failed_checks = 0
    unverified_checks = 0
    
    company_pass_map = {}
    
    for comp in sorted(companies, key=lambda c: (c.peer_group_id, c.ticker)):
        facts = get_facts_for_company(comp.ticker)
        results = FundamentalsValidator.validate_company_dataset(
            comp, facts, sources, coverage=coverage, evidence_register=evidence_register
        )
        
        company_passed = True
        print(f"\n[{comp.ticker}] {comp.name} ({comp.peer_group_name}) — {len(facts)} periods")
        
        for r in results:
            total_checks += 1
            if r.status == ValidationStatus.FAIL:
                status_icon = "FAIL"
                failed_checks += 1
                company_passed = False
            elif r.status == ValidationStatus.UNVERIFIED:
                status_icon = "UNVERIFIED"
                unverified_checks += 1
                company_passed = False
            elif r.status == ValidationStatus.WARNING:
                status_icon = "WARNING"
                warning_checks += 1
            else:
                status_icon = "PASS"
                passed_checks += 1
                
            print(f"  [{status_icon:10}] {r.rule_name}: {r.message}")
            if r.details.get("warnings"):
                for w in r.details["warnings"]:
                    print(f"               * REVIEW FLAG: {w}")
                    
        company_pass_map[comp.ticker] = company_passed

    dim_summary = {}
    for comp in sorted(companies, key=lambda c: (c.peer_group_id, c.ticker)):
        facts = get_facts_for_company(comp.ticker)
        results = FundamentalsValidator.validate_company_dataset(
            comp, facts, sources, coverage=coverage, evidence_register=evidence_register
        )
        for r in results:
            d = r.dimension or "STRUCTURAL"
            if d not in dim_summary:
                dim_summary[d] = {"PASS": 0, "WARNING": 0, "FAIL": 0, "UNVERIFIED": 0}
            dim_summary[d][r.status.value] = dim_summary[d].get(r.status.value, 0) + 1

    computational_passed = dim_summary.get("COMPUTATIONAL", {}).get("PASS", 0)
    computational_total = sum(dim_summary.get("COMPUTATIONAL", {}).values())
    lineage_passed = dim_summary.get("SOURCE_LINEAGE", {}).get("PASS", 0)
    lineage_total = sum(dim_summary.get("SOURCE_LINEAGE", {}).values())
    coverage_passed = dim_summary.get("COVERAGE_INTEGRITY", {}).get("PASS", 0)
    coverage_total = sum(dim_summary.get("COVERAGE_INTEGRITY", {}).values())
    comparability_passed = dim_summary.get("COMPARABILITY_INTEGRITY", {}).get("PASS", 0)
    comparability_total = sum(dim_summary.get("COMPARABILITY_INTEGRITY", {}).values())
    structural_passed = dim_summary.get("STRUCTURAL", {}).get("PASS", 0)
    structural_total = sum(dim_summary.get("STRUCTURAL", {}).values())

    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY & EVIDENCE AUDIT TRAIL")
    print("=" * 80)
    print(f"Total Companies Evaluated:               {len(companies)}")
    print(f"Total Checks Executed:                   {total_checks}")
    print(f"Total Passed:                            {passed_checks}")
    print(f"Total Warnings:                          {warning_checks}")
    print(f"Total Failed:                            {failed_checks}")
    print(f"Total Unverified:                        {unverified_checks}")
    print(f"Companies Passing 100% Gates:            {sum(company_pass_map.values())} / {len(companies)}")
    print("-" * 80)
    print("MULTI-DIMENSIONAL AUDIT BREAKDOWN:")
    print(f"1. Structural Integrity Passed:          {structural_passed} / {structural_total} (Completeness, Uniqueness, ISO Date Format)")
    print(f"2. Computational Checks Passed:          {computational_passed} / {computational_total} (Operating Margins, Capex Non-Negative Signs, FCF)")
    print(f"3. Source Lineage & Links Validated:     {lineage_passed} / {lineage_total} (Filing URLs, Accessions, Reference Typing, Tiers)")
    print(f"4. Coverage Integrity Passed:            {coverage_passed} / {coverage_total} (Target Horizon Semantics & Chronology)")
    print(f"5. Comparability & Definitions Passed:   {comparability_passed} / {comparability_total} (Standardized GAAP & Ind AS Taxonomy)")
    print(f"6. Primary Metrics Reconciled:           {counts['independently_reconciled']} / {counts['total_primary_metrics']} ({counts['independently_reconciled'] / counts['total_primary_metrics'] * 100:.1f}%), {counts['source_linked_only']} source-linked only, {counts['unverified']} unverified")
    print(f"7. Sourced Periods with Discrepancy Log: {len(discrepancies)} documented items (Stored in discrepancy_ledger.json)")
    print("=" * 80)
    
    if failed_checks > 0 or unverified_checks > 0:
        print("RESULT: VALIDATION GATES FAILED")
        return 1
    else:
        print("RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)")
        return 0


if __name__ == "__main__":
    sys.exit(run_validation())
