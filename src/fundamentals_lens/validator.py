from datetime import date
from typing import List, Dict, Any, Optional
import re

from .models import (
    Company,
    FinancialFact,
    DerivedMetrics,
    ValidationResult,
    ValidationStatus,
    VerificationTier,
    normalize_verification_tier
)
from .metrics import compute_derived_metrics_for_company


class FundamentalsValidator:
    """
    Deterministic data integrity validation framework for Fundamentals Lens (Phase 5 Hardened).
    Evaluates datasets against structural, reporting standards, source provenance,
    computational invariants, coverage integrity, accounting comparability, and anomaly review.
    """

    @classmethod
    def validate_company_dataset(
        cls, 
        company: Company, 
        facts: List[FinancialFact],
        sources: Optional[List[Dict[str, Any]]] = None,
        coverage: Optional[List[Dict[str, Any]]] = None,
        derived_metrics: Optional[List[DerivedMetrics]] = None,
        evidence_register: Optional[List[Dict[str, Any]]] = None
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        
        # Dimension 1: Structural Integrity (Completeness, Chronology, Uniqueness, Dates)
        results.append(cls._check_period_completeness(company, facts))
        results.append(cls._check_duplicate_observations(facts))
        results.append(cls._check_period_date_formats(facts))
        
        # Dimension 2: Reporting Standards Integrity (Currency, Scale, Non-Coercion)
        results.append(cls._check_currency_and_unit_consistency(company, facts))
        results.append(cls._check_non_coercion_to_zero(facts))
        
        # Dimension 3: Source Lineage & Provenance Traceability
        results.extend(cls._check_source_provenance(facts, sources))
        results.append(cls._check_filing_reference_types(facts))
        
        # Dimension 4: Computational & Arithmetic Invariants
        results.extend(cls._check_arithmetic_invariants(facts, derived_metrics=derived_metrics))
        
        # Dimension 5: Coverage & Target Horizon Integrity
        results.append(cls._check_coverage_integrity(company, coverage, facts=facts))

        # Dimension 6: Accounting Definition & Comparability Integrity
        results.append(cls._check_comparability_integrity(company))
        results.append(cls._check_metric_definitions(facts, sources))
        
        # Dimension 7: Evidence Alignment & Reconciliation Tiers (Phase 6 Hardened)
        if evidence_register is None:
            try:
                from .data_loader import load_evidence_register
                evidence_register = load_evidence_register()
            except Exception:
                evidence_register = None
        results.extend(cls._check_evidence_alignment_and_tiers(facts, evidence_register))
        
        # Dimension 8: Statistical Anomaly & Outlier Review (Non-destructive)
        results.extend(cls._check_anomalies_and_variances(facts))
        
        return results

    @staticmethod
    def _check_period_completeness(company: Company, facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_PERIOD_COMPLETENESS"
        rule_name = "Five-Period Consecutive Completeness & Chronology"
        
        if len(facts) != 5:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Company {company.ticker} has {len(facts)} verified periods (requires 5 consecutive periods).",
                details={"actual_periods": [f.fiscal_year_label for f in facts]},
                dimension="STRUCTURAL"
            )
            
        sorted_facts = sorted(facts, key=lambda f: f.fiscal_year)
        sorted_years = [f.fiscal_year for f in sorted_facts]
        
        # 1. Check consecutive years
        for i in range(1, len(sorted_years)):
            if sorted_years[i] != sorted_years[i-1] + 1:
                return ValidationResult(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    status=ValidationStatus.FAIL,
                    message=f"Gap detected in fiscal periods for {company.ticker}: {sorted_years}",
                    details={"years": sorted_years},
                    dimension="STRUCTURAL"
                )
                
        # 2. Check chronological period dates
        for i, f in enumerate(sorted_facts):
            if f.period_start and f.period_end:
                if f.period_start >= f.period_end:
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Period start ({f.period_start}) must precede period end ({f.period_end}) for {company.ticker} {f.fiscal_year_label}.",
                        details={"period_start": f.period_start, "period_end": f.period_end},
                        dimension="STRUCTURAL"
                    )
            if i > 0:
                prev = sorted_facts[i-1]
                if f.period_end <= prev.period_end:
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Chronological ordering violation for {company.ticker}: {f.fiscal_year_label} ({f.period_end}) <= {prev.fiscal_year_label} ({prev.period_end}).",
                        details={"current": f.period_end, "previous": prev.period_end},
                        dimension="STRUCTURAL"
                    )

        # 3. Check fiscal year label matches fiscal year
        for f in sorted_facts:
            yr_str = str(f.fiscal_year)
            short_yr = yr_str[-2:]
            # FY2021 or FY 2021-22
            if yr_str not in f.fiscal_year_label and short_yr not in f.fiscal_year_label:
                return ValidationResult(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    status=ValidationStatus.FAIL,
                    message=f"Fiscal year label '{f.fiscal_year_label}' does not correspond to fiscal_year {f.fiscal_year} for {company.ticker}.",
                    details={"fiscal_year": f.fiscal_year, "fiscal_year_label": f.fiscal_year_label},
                    dimension="STRUCTURAL"
                )

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Exactly 5 consecutive annual periods verified for {company.ticker} ({sorted_facts[0].fiscal_year_label} to {sorted_facts[-1].fiscal_year_label}).",
            details={"periods": [f.fiscal_year_label for f in sorted_facts]},
            dimension="STRUCTURAL"
        )

    @staticmethod
    def _check_currency_and_unit_consistency(company: Company, facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_UNIT_CONSISTENCY"
        rule_name = "Currency and Unit Consistency"
        
        currencies = {f.currency for f in facts}
        units = {f.unit for f in facts}
        scales = {f.scale_multiplier for f in facts}
        
        if len(currencies) > 1 or (currencies and list(currencies)[0] != company.reporting_currency):
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Currency mismatch for {company.ticker}: expected {company.reporting_currency}, found {currencies}",
                details={"found_currencies": list(currencies)},
                dimension="REPORTING_STANDARDS"
            )
            
        if len(units) > 1 or len(scales) > 1 or (units and list(units)[0] != company.standard_unit_label) or (scales and list(scales)[0] != company.scale_multiplier):
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Mixed scale multipliers or unit labels detected for {company.ticker}: {units}, {scales} (expected {company.standard_unit_label}, {company.scale_multiplier})",
                details={"units": list(units), "scales": list(scales)},
                dimension="REPORTING_STANDARDS"
            )
            
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Consistent currency ({company.reporting_currency}) and units ({company.standard_unit_label}) across all periods.",
            details={"currency": company.reporting_currency, "unit": company.standard_unit_label},
            dimension="REPORTING_STANDARDS"
        )

    @staticmethod
    def _check_duplicate_observations(facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_NO_DUPLICATES"
        rule_name = "Observation Uniqueness"
        
        seen_years = set()
        seen_dates = set()
        seen_accessions = set()
        duplicates = []
        for f in facts:
            year_key = (f.ticker, f.fiscal_year)
            date_key = (f.ticker, f.period_end)
            acc_key = (f.ticker, f.accession_id)
            if year_key in seen_years:
                duplicates.append(f"Year duplicate: {year_key}")
            if date_key in seen_dates:
                duplicates.append(f"Period end duplicate: {date_key}")
            if acc_key in seen_accessions:
                duplicates.append(f"Accession duplicate across periods: {acc_key}")
            seen_years.add(year_key)
            seen_dates.add(date_key)
            seen_accessions.add(acc_key)
            
        if duplicates:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Duplicate observation keys detected: {duplicates}",
                details={"duplicates": duplicates},
                dimension="STRUCTURAL"
            )
            
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message="Zero duplicate observation records found; strictly one record per fiscal year, unique period end date, and unique accession.",
            details={"record_count": len(facts)},
            dimension="STRUCTURAL"
        )

    @staticmethod
    def _check_non_coercion_to_zero(facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_NON_COERCION"
        rule_name = "Missing Data Non-Coercion Guard"
        
        # Invariant: Missing values must remain None/missing, never coerced to 0.0.
        # Zero revenue in mature listed companies is considered suspicious unless documented.
        # Zero capex is allowed if explicitly supported by primary disclosure notes.
        suspicious_zeros = []
        disclosed_zeros = []
        missing_values = []

        for f in facts:
            # Check for None values in mandatory primary metrics
            for m in ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"):
                val = getattr(f, m, None)
                if val is None:
                    missing_values.append((f.fiscal_year_label, m))

            if f.revenue is not None and f.revenue <= 0.0:
                if not f.notes or "zero revenue" not in f.notes.lower():
                    suspicious_zeros.append((f.fiscal_year_label, "revenue (unexplained non-positive)"))
            if f.capital_expenditure is not None and f.capital_expenditure == 0.0:
                notes_text = (f.notes or "") + " " + (getattr(f, "accounting_notes", "") or "")
                if "zero capex" in notes_text.lower() or "no capital expenditure" in notes_text.lower():
                    disclosed_zeros.append((f.fiscal_year_label, "capex (disclosed zero)"))
                else:
                    suspicious_zeros.append((f.fiscal_year_label, "capital_expenditure (unexplained zero)"))
                
        if missing_values:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Mandatory primary financial metrics missing (None) without documented justification: {missing_values}",
                details={"missing_values": missing_values},
                dimension="REPORTING_STANDARDS"
            )

        if suspicious_zeros:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Potential synthetic zero coercion detected in observations: {suspicious_zeros}",
                details={"suspicious_zeros": suspicious_zeros},
                dimension="REPORTING_STANDARDS"
            )
            
        msg = "No suspicious zero coercions detected in primary disclosures."
        if disclosed_zeros:
            msg += f" Valid disclosed zeroes verified: {disclosed_zeros}."

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=msg,
            details={"disclosed_zeros": disclosed_zeros},
            dimension="REPORTING_STANDARDS"
        )

    @staticmethod
    def _check_source_provenance(
        facts: List[FinancialFact], 
        sources: Optional[List[Dict[str, Any]]]
    ) -> List[ValidationResult]:
        results = []
        rule_id = "GATE_SOURCE_PROVENANCE"
        rule_name = "Primary Source Lineage and Traceability"
        
        missing_urls = []
        generic_urls = []
        missing_locations = []
        unverified_facts = []
        register_mismatches = []

        # Disallowed generic URL patterns: browse portals, root domains without documents, bare landing pages
        generic_url_patterns = [
            r"sec\.gov/edgar/browse",
            r"https?://www\.[a-z0-9\-]+\.(com|co\.in|in)/?$", # bare domain root
            r"https?://www\.[a-z0-9\-]+\.(com|co\.in|in)/investors/?$", # generic root /investors
            r"https?://www\.[a-z0-9\-]+\.(com|co\.in|in)/investor-relations/?$", # generic root /investor-relations
            r"https?://www\.[a-z0-9\-]+\.(com|co\.in|in)/corporate/investors/?$" # generic root /corporate/investors
        ]

        for f in facts:
            url = f.source_url or ""
            if not url or not url.startswith("http"):
                missing_urls.append(f.fiscal_year_label)
            
            for pat in generic_url_patterns:
                if re.search(pat, url, re.IGNORECASE):
                    generic_urls.append((f.fiscal_year_label, url))
                    break

            if not f.statement_location or len(f.statement_location.strip()) < 5:
                missing_locations.append(f.fiscal_year_label)
            if f.verification_status != "VERIFIED":
                unverified_facts.append(f.fiscal_year_label)

        if missing_urls:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Missing or invalid primary source URLs in periods: {missing_urls}",
                details={"missing_urls": missing_urls},
                dimension="SOURCE_LINEAGE"
            ))
            return results

        if generic_urls:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Generic search/browse or bare landing URLs detected instead of specific filing document URLs: {generic_urls}",
                details={"generic_urls": generic_urls},
                dimension="SOURCE_LINEAGE"
            ))
            return results

        if missing_locations:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Missing statement page or line-item locations in periods: {missing_locations}",
                details={"missing_locations": missing_locations},
                dimension="SOURCE_LINEAGE"
            ))
            return results

        if unverified_facts:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.UNVERIFIED,
                message=f"Observations not marked as VERIFIED: {unverified_facts}",
                details={"unverified_facts": unverified_facts},
                dimension="SOURCE_LINEAGE"
            ))
            return results

        if not sources:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.UNVERIFIED,
                message="Source register metadata unprovided; offline provenance lineage unverified.",
                dimension="SOURCE_LINEAGE"
            ))
            return results

        source_map = {(s["ticker"], s["fiscal_year_label"]): s for s in sources}
        for f in facts:
            # Cross-verify against source register
            k = (f.ticker, f.fiscal_year_label)
            s = source_map.get(k)
            if not s:
                register_mismatches.append(f"No source register entry for {k}")
            else:
                if f.source_id != s.get("source_id"):
                    register_mismatches.append(f"{k}: fact source_id '{f.source_id}' != register '{s.get('source_id')}'")
                if f.source_url != s.get("source_url"):
                    register_mismatches.append(f"{k}: fact source_url != register source_url")
                if f.accession_id != s.get("accession_id"):
                    register_mismatches.append(f"{k}: fact accession_id '{f.accession_id}' != register '{s.get('accession_id')}'")
                if not s.get("line_item_mappings"):
                    register_mismatches.append(f"{k}: missing line_item_mappings in source register")
                if not s.get("metric_definitions"):
                    register_mismatches.append(f"{k}: missing metric_definitions in source register")
                
        if register_mismatches:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Source register alignment mismatches detected: {register_mismatches[:3]}",
                details={"mismatches": register_mismatches},
                dimension="SOURCE_LINEAGE"
            ))
        else:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.PASS,
                message="100% of observations link to primary filings with verified statement locations, valid accession IDs, and exact source register alignment.",
                details={"verified_count": len(facts), "lineage_note": "Verified against primary document citations and offline accession registry."},
                dimension="SOURCE_LINEAGE"
            ))
            
        return results

    @staticmethod
    def _check_arithmetic_invariants(
        facts: List[FinancialFact],
        derived_metrics: Optional[List[DerivedMetrics]] = None
    ) -> List[ValidationResult]:
        results = []
        derived_list = derived_metrics if derived_metrics is not None else compute_derived_metrics_for_company(facts)
        
        # 1. Operating Margin Invariant Check
        margin_errors = []
        for fact, derived in zip(facts, derived_list):
            if fact.revenue > 0:
                expected = round((fact.operating_income / fact.revenue) * 100.0, 2)
                if fact.operating_income > fact.revenue:
                    margin_errors.append((fact.fiscal_year_label, f"Operating income ({fact.operating_income}) exceeds revenue ({fact.revenue})"))
                elif derived.operating_margin is not None and abs(derived.operating_margin - expected) > 0.05:
                    margin_errors.append((fact.fiscal_year_label, derived.operating_margin, expected))
                    
        if margin_errors:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_OPERATING_MARGIN",
                rule_name="Operating Margin Arithmetic Invariant",
                status=ValidationStatus.FAIL,
                message=f"Operating margin reconciliation mismatch: {margin_errors}",
                details={"errors": margin_errors},
                dimension="COMPUTATIONAL"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_OPERATING_MARGIN",
                rule_name="Operating Margin Arithmetic Invariant",
                status=ValidationStatus.PASS,
                message="Operating margin reconciles to (Operating Income / Revenue) within 0.05% tolerance.",
                details={},
                dimension="COMPUTATIONAL"
            ))
            
        # 2. Free Cash Flow & Capex Sign Invariants
        fcf_errors = []
        capex_sign_errors = []
        for fact, derived in zip(facts, derived_list):
            if fact.capital_expenditure < 0:
                capex_sign_errors.append((fact.fiscal_year_label, fact.capital_expenditure))
            if derived.free_cash_flow is not None:
                expected_fcf = round(fact.operating_cash_flow - fact.capital_expenditure, 2)
                if abs(derived.free_cash_flow - expected_fcf) > 0.001:
                    fcf_errors.append((fact.fiscal_year_label, derived.free_cash_flow, expected_fcf))
                    
        if capex_sign_errors:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_CAPEX_SIGN",
                rule_name="Capital Expenditure Non-Negative Sign Invariant",
                status=ValidationStatus.FAIL,
                message=f"Capex must be expressed as a non-negative cash outflow magnitude: {capex_sign_errors}",
                details={"errors": capex_sign_errors},
                dimension="COMPUTATIONAL"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_CAPEX_SIGN",
                rule_name="Capital Expenditure Non-Negative Sign Invariant",
                status=ValidationStatus.PASS,
                message="All capital expenditures conform to positive magnitude cash outflow convention.",
                details={},
                dimension="COMPUTATIONAL"
            ))

        if fcf_errors:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_FCF",
                rule_name="Free Cash Flow Reconciliation Invariant",
                status=ValidationStatus.FAIL,
                message=f"Free cash flow reconciliation mismatch (OCF - Capex): {fcf_errors}",
                details={"errors": fcf_errors},
                dimension="COMPUTATIONAL"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_ARITHMETIC_FCF",
                rule_name="Free Cash Flow Reconciliation Invariant",
                status=ValidationStatus.PASS,
                message="Free cash flow reconciles exactly to (Operating Cash Flow - Capex).",
                details={},
                dimension="COMPUTATIONAL"
            ))
            
        return results

    @staticmethod
    def _check_coverage_integrity(
        company: Company, 
        coverage: Optional[List[Dict[str, Any]]],
        facts: Optional[List[FinancialFact]] = None
    ) -> ValidationResult:
        rule_id = "GATE_COVERAGE_INTEGRITY"
        rule_name = "Target Horizon Coverage & Non-Fabrication Audit"
        
        if not coverage:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.UNVERIFIED,
                message=f"Coverage metadata unprovided for {company.ticker}; status unverified.",
                dimension="COVERAGE_INTEGRITY"
            )
            
        cov_matches = [c for c in coverage if c.get("ticker") == company.ticker]
        if not cov_matches:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Missing coverage report entry for {company.ticker}.",
                dimension="COVERAGE_INTEGRITY"
            )
        if len(cov_matches) > 1:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Duplicate coverage report entries detected for {company.ticker}.",
                dimension="COVERAGE_INTEGRITY"
            )
            
        cov = cov_matches[0]
        code = cov.get("target_period_status_code")
        target_period = cov.get("target_horizon_period")
        claimed_periods = cov.get("verified_periods", [])
        latest_verified = cov.get("latest_verified_period")
        status_desc = cov.get("target_period_status_desc", "")
        overall_status = cov.get("overall_coverage_status", "")

        if code not in (0, 1, 2):
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Invalid target period status code {code} for {company.ticker}.",
                dimension="COVERAGE_INTEGRITY"
            )

        # Cross-validate against actual dataset facts
        if facts:
            sorted_facts = sorted(facts, key=lambda x: x.fiscal_year)
            actual_periods = [f.fiscal_year_label for f in sorted_facts]
            actual_latest = sorted_facts[-1].fiscal_year_label if sorted_facts else None

            if claimed_periods != actual_periods:
                return ValidationResult(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    status=ValidationStatus.FAIL,
                    message=f"Coverage verified periods mismatch for {company.ticker}: claimed {claimed_periods} != actual {actual_periods}",
                    details={"claimed": claimed_periods, "actual": actual_periods},
                    dimension="COVERAGE_INTEGRITY"
                )

            if latest_verified != actual_latest:
                return ValidationResult(
                    rule_id=rule_id,
                    rule_name=rule_name,
                    status=ValidationStatus.FAIL,
                    message=f"Latest verified period mismatch for {company.ticker}: claimed {latest_verified} != actual {actual_latest}",
                    details={"claimed_latest": latest_verified, "actual_latest": actual_latest},
                    dimension="COVERAGE_INTEGRITY"
                )

            # Validate status semantics
            if code == 0:
                if target_period not in actual_periods:
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Status code 0 claims target horizon {target_period} is included, but it is not in actual periods for {company.ticker}.",
                        dimension="COVERAGE_INTEGRITY"
                    )
                if overall_status != "5_PERIODS_VERIFIED_TARGET_HORIZON_INCLUDED":
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Inconsistent overall status '{overall_status}' for status code 0 on {company.ticker}.",
                        dimension="COVERAGE_INTEGRITY"
                    )
            elif code == 1:
                if target_period in actual_periods:
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Status code 1 claims target horizon {target_period} is pending, but it is already in verified periods for {company.ticker}.",
                        dimension="COVERAGE_INTEGRITY"
                    )
                if overall_status != "5_PERIODS_VERIFIED_TARGET_HORIZON_PENDING":
                    return ValidationResult(
                        rule_id=rule_id,
                        rule_name=rule_name,
                        status=ValidationStatus.FAIL,
                        message=f"Inconsistent overall status '{overall_status}' for status code 1 on {company.ticker}.",
                        dimension="COVERAGE_INTEGRITY"
                    )

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Coverage verified ({len(claimed_periods)} periods): Target horizon {target_period} status code {code} ({overall_status}).",
            details=cov,
            dimension="COVERAGE_INTEGRITY"
        )

    @staticmethod
    def _check_comparability_integrity(company: Company) -> ValidationResult:
        rule_id = "GATE_COMPARABILITY_INTEGRITY"
        rule_name = "Peer Comparability & Structural Nuance Registration"
        if not company.peer_group_id:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Company {company.ticker} is missing peer group assignment.",
                dimension="COMPARABILITY_INTEGRITY"
            )
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Peer group '{company.peer_group_name}' registered with documented business caveats.",
            details={"peer_group_id": company.peer_group_id},
            dimension="COMPARABILITY_INTEGRITY"
        )

    @staticmethod
    def _check_metric_definitions(
        facts: List[FinancialFact], 
        sources: Optional[List[Dict[str, Any]]]
    ) -> ValidationResult:
        rule_id = "GATE_METRIC_DEFINITIONS"
        rule_name = "Accounting Metric Definitions & Comparability Nuance"

        if not sources:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.UNVERIFIED,
                message="Source register not provided; metric definitions cannot be verified.",
                dimension="COMPARABILITY_INTEGRITY"
            )

        allowed_oi_types = {"US_GAAP_OPERATING_INCOME", "IND_AS_EBIT_OPERATING_PROFIT", "IND_AS_PBEI_PROXY"}
        allowed_capex_types = {"PPE_PURCHASES_ONLY", "PPE_AND_CWIP", "PPE_AND_INTANGIBLES"}
        allowed_comp_flags = {"DIRECT", "PROXY", "LIMITED", "NOT_COMPARABLE"}

        def_errors = []
        source_map = {(s["ticker"], s["fiscal_year_label"]): s for s in sources}

        for f in facts:
            k = (f.ticker, f.fiscal_year_label)
            src = source_map.get(k)
            if not src:
                def_errors.append(f"Missing source entry for {k}")
                continue

            mdefs = src.get("metric_definitions")
            if not mdefs:
                def_errors.append(f"Missing metric_definitions for {k}")
                continue

            oi_type = mdefs.get("operating_income_type")
            capex_type = mdefs.get("capex_type")
            oi_comp = mdefs.get("operating_income_comparability")
            capex_comp = mdefs.get("capex_comparability")
            overall_comp = mdefs.get("overall_comparability")

            if oi_type not in allowed_oi_types:
                def_errors.append(f"Invalid operating_income_type '{oi_type}' in {k}")
            if capex_type not in allowed_capex_types:
                def_errors.append(f"Invalid capex_type '{capex_type}' in {k}")
            if oi_comp not in allowed_comp_flags:
                def_errors.append(f"Invalid operating_income_comparability '{oi_comp}' in {k}")
            if capex_comp not in allowed_comp_flags:
                def_errors.append(f"Invalid capex_comparability '{capex_comp}' in {k}")
            if overall_comp not in allowed_comp_flags:
                def_errors.append(f"Invalid overall_comparability '{overall_comp}' in {k}")

            # Specific rule: If Ind AS PBEI proxy, comparability must be PROXY
            if oi_type == "IND_AS_PBEI_PROXY" and oi_comp != "PROXY":
                def_errors.append(f"PBEI proxy must have comparability flag 'PROXY' in {k}")

            # Fact comparability flag must match source overall_comparability
            fact_comp = getattr(f, "comparability_flag", None)
            if fact_comp and fact_comp != overall_comp:
                def_errors.append(f"Fact comparability_flag '{fact_comp}' != source '{overall_comp}' in {k}")

        if def_errors:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Accounting metric definition errors: {def_errors[:3]}",
                details={"errors": def_errors},
                dimension="COMPARABILITY_INTEGRITY"
            )

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message="All observations have documented canonical accounting definitions and peer comparability flags.",
            details={"observation_count": len(facts)},
            dimension="COMPARABILITY_INTEGRITY"
        )

    @staticmethod
    def _check_anomalies_and_variances(facts: List[FinancialFact]) -> List[ValidationResult]:
        results = []
        derived_list = compute_derived_metrics_for_company(facts)
        warnings = []
        
        for i in range(1, len(derived_list)):
            curr = derived_list[i]
            prior = derived_list[i - 1]
            
            # Anomaly check: Margin shift > 20 percentage points
            if curr.operating_margin is not None and prior.operating_margin is not None:
                shift = abs(curr.operating_margin - prior.operating_margin)
                if shift > 20.0:
                    warnings.append(f"{curr.fiscal_year_label}: Operating margin shifted by {shift:.2f}% (from {prior.operating_margin}% to {curr.operating_margin}%)")
                    
            # Anomaly check: Revenue contraction > 50%
            if curr.revenue_growth_yoy is not None and curr.revenue_growth_yoy < -50.0:
                warnings.append(f"{curr.fiscal_year_label}: Severe revenue contraction of {curr.revenue_growth_yoy:.2f}%")
                
        if warnings:
            results.append(ValidationResult(
                rule_id="GATE_ANOMALY_SCAN",
                rule_name="Statistical Outlier and Variance Scan",
                status=ValidationStatus.WARNING,
                message=f"Statistical anomaly flagged for analyst review ({len(warnings)} variances detected).",
                details={"warnings": warnings},
                dimension="ANOMALY_REVIEW"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_ANOMALY_SCAN",
                rule_name="Statistical Outlier and Variance Scan",
                status=ValidationStatus.PASS,
                message="No unusual multi-year margin or revenue shocks detected.",
                details={},
                dimension="ANOMALY_REVIEW"
            ))
            
        return results

    @staticmethod
    def _check_period_date_formats(facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_PERIOD_DATE_FORMAT"
        rule_name = "ISO Period Date Formatting and Semantics"
        errors = []
        date_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}$")

        for f in facts:
            start_str = str(f.period_start) if f.period_start else ""
            end_str = str(f.period_end) if f.period_end else ""

            if not date_pattern.match(start_str):
                errors.append(f"{f.ticker} {f.fiscal_year_label}: Invalid period_start date format '{start_str}'")
            if not date_pattern.match(end_str):
                errors.append(f"{f.ticker} {f.fiscal_year_label}: Invalid period_end date format '{end_str}'")

        if errors:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Invalid period date formats detected: {errors[:3]}",
                details={"errors": errors},
                dimension="STRUCTURAL"
            )

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message="All period start and end dates conform to strict ISO 8601 YYYY-MM-DD format.",
            details={"observation_count": len(facts)},
            dimension="STRUCTURAL"
        )

    @staticmethod
    def _check_filing_reference_types(facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_REFERENCE_TYPE_INTEGRITY"
        rule_name = "Filing Reference Type and Accession Integrity"
        errors = []

        sec_accession_pattern = re.compile(r"^\d{10}-\d{2}-\d{6}$")

        for f in facts:
            ref_type = getattr(f, "reference_type", None)
            acc_id = getattr(f, "accession_id", None)
            official_id = getattr(f, "official_filing_id", None)
            internal_key = getattr(f, "internal_document_key", None)

            if not ref_type or ref_type not in ("SEC_ACCESSION", "INTERNAL_DOCUMENT_KEY", "EXCHANGE_FILING_ID"):
                errors.append(f"{f.ticker} {f.fiscal_year_label}: Invalid or missing reference_type '{ref_type}'")
                continue

            if ref_type == "SEC_ACCESSION":
                if not acc_id or not sec_accession_pattern.match(acc_id):
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: SEC accession '{acc_id}' does not match standard 20-digit pattern")
                if acc_id and (acc_id.startswith("BSE-") or acc_id.startswith("NSE-") or "INTERNAL" in acc_id):
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: Internal document key '{acc_id}' falsely labeled as SEC_ACCESSION")
                if official_id and official_id != acc_id:
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: official_filing_id '{official_id}' != accession_id '{acc_id}'")
                if internal_key is not None:
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: SEC_ACCESSION record has internal_document_key set: {internal_key}")

            elif ref_type == "INTERNAL_DOCUMENT_KEY":
                if not internal_key or len(internal_key.strip()) < 5:
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: Missing internal_document_key for INTERNAL_DOCUMENT_KEY reference type")
                if official_id is not None:
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: INTERNAL_DOCUMENT_KEY record falsely claims official_filing_id '{official_id}'")
                if acc_id and sec_accession_pattern.match(acc_id):
                    errors.append(f"{f.ticker} {f.fiscal_year_label}: SEC accession format used with INTERNAL_DOCUMENT_KEY type")

        if errors:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Filing reference type integrity violations: {errors[:3]}",
                details={"errors": errors},
                dimension="SOURCE_LINEAGE"
            )

        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message="All observations have strictly typed filing references (SEC accession vs internal document keys).",
            details={"observation_count": len(facts)},
            dimension="SOURCE_LINEAGE"
        )

    @staticmethod
    def _check_evidence_alignment_and_tiers(
        facts: List[FinancialFact],
        evidence_register: Optional[List[Dict[str, Any]]]
    ) -> List[ValidationResult]:
        results = []
        
        if evidence_register is None:
            results.append(ValidationResult(
                rule_id="GATE_FACT_EVIDENCE_ALIGNMENT",
                rule_name="Fact-to-Evidence Exact Alignment",
                status=ValidationStatus.UNVERIFIED,
                message="Evidence register not provided; exact fact-to-evidence cross-verification skipped.",
                dimension="SOURCE_LINEAGE"
            ))
            return results

        evidence_map = {}
        for reg in evidence_register:
            key = (reg.get("ticker"), reg.get("fiscal_year_label"))
            evidence_map[key] = reg
            yr_key = (reg.get("ticker"), reg.get("fiscal_year"))
            evidence_map[yr_key] = reg

        alignment_errors = []
        tier_errors = []
        primary_metrics = ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure")

        for f in facts:
            key = (f.ticker, f.fiscal_year_label)
            reg = evidence_map.get(key) or evidence_map.get((f.ticker, f.fiscal_year))
            if not reg:
                alignment_errors.append(f"No evidence register entry found for {f.ticker} {f.fiscal_year_label}")
                continue

            metrics = reg.get("metrics", {})
            for m in primary_metrics:
                m_ev = metrics.get(m)
                if not m_ev:
                    alignment_errors.append(f"Missing metric evidence for {f.ticker} {f.fiscal_year_label} ({m})")
                    continue

                fact_val = getattr(f, m, None)
                canon_val = m_ev.get("canonical_value")

                if fact_val is None or canon_val is None:
                    alignment_errors.append(f"{f.ticker} {f.fiscal_year_label} {m}: Fact value or evidence canonical value is None")
                elif abs(fact_val - canon_val) > 0.001:
                    alignment_errors.append(
                        f"{f.ticker} {f.fiscal_year_label} {m}: Fact value {fact_val} != Evidence canonical value {canon_val}"
                    )

                tier = m_ev.get("reconciliation_tier")
                norm_tier = normalize_verification_tier(tier)
                if norm_tier == VerificationTier.INDEPENDENTLY_RECONCILED.value:
                    loc = m_ev.get("statement_locator") or ""
                    line_item = m_ev.get("reported_line_item") or ""
                    stmt_name = m_ev.get("statement_name") or ""
                    if len(loc.strip()) < 5:
                        tier_errors.append(f"{f.ticker} {f.fiscal_year_label} {m}: Missing or inadequate statement locator for reconciled tier")
                    if len(line_item.strip()) < 3:
                        tier_errors.append(f"{f.ticker} {f.fiscal_year_label} {m}: Missing reported line item for reconciled tier")
                    if len(stmt_name.strip()) < 3:
                        tier_errors.append(f"{f.ticker} {f.fiscal_year_label} {m}: Missing statement name for reconciled tier")

        if alignment_errors:
            results.append(ValidationResult(
                rule_id="GATE_FACT_EVIDENCE_ALIGNMENT",
                rule_name="Fact-to-Evidence Exact Alignment",
                status=ValidationStatus.FAIL,
                message=f"Discrepancies detected between financial facts and primary evidence register: {alignment_errors[:3]}",
                details={"errors": alignment_errors},
                dimension="SOURCE_LINEAGE"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_FACT_EVIDENCE_ALIGNMENT",
                rule_name="Fact-to-Evidence Exact Alignment",
                status=ValidationStatus.PASS,
                message="All primary financial facts match evidence register canonical values within 0.001 tolerance.",
                details={"verified_periods": len(facts)},
                dimension="SOURCE_LINEAGE"
            ))

        if tier_errors:
            results.append(ValidationResult(
                rule_id="GATE_EVIDENCE_TIER_CONSISTENCY",
                rule_name="Evidence Verification Tier Consistency",
                status=ValidationStatus.FAIL,
                message=f"Reconciliation tier requirements violated: {tier_errors[:3]}",
                details={"tier_errors": tier_errors},
                dimension="SOURCE_LINEAGE"
            ))
        else:
            results.append(ValidationResult(
                rule_id="GATE_EVIDENCE_TIER_CONSISTENCY",
                rule_name="Evidence Verification Tier Consistency",
                status=ValidationStatus.PASS,
                message="All reconciled metric tiers have documented statement names, line items, and audit locators.",
                details={"reconciled_check": "passed"},
                dimension="SOURCE_LINEAGE"
            ))

        return results

    @classmethod
    def get_metric_verification_counts(
        cls, 
        evidence_register: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, int]:
        if evidence_register is None:
            try:
                from .data_loader import load_evidence_register
                evidence_register = load_evidence_register()
            except Exception:
                evidence_register = []

        reconciled = 0
        source_linked = 0
        unverified = 0
        failed = 0
        total_primary = 0
        fcf_derived = 0

        primary_metrics = ("revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure")

        for reg in evidence_register:
            metrics = reg.get("metrics", {})
            has_reconciled_ocf = False
            has_reconciled_capex = False

            for m in primary_metrics:
                m_ev = metrics.get(m)
                if not m_ev:
                    continue
                total_primary += 1
                tier = m_ev.get("reconciliation_tier")
                norm_tier = normalize_verification_tier(tier)
                if norm_tier == VerificationTier.INDEPENDENTLY_RECONCILED.value:
                    reconciled += 1
                    if m == "operating_cash_flow":
                        has_reconciled_ocf = True
                    elif m == "capital_expenditure":
                        has_reconciled_capex = True
                elif norm_tier == VerificationTier.SOURCE_LINKED_ONLY.value:
                    source_linked += 1
                elif norm_tier == VerificationTier.FAILED.value:
                    failed += 1
                else:
                    unverified += 1

            fcf_entry = metrics.get("free_cash_flow")
            if fcf_entry and normalize_verification_tier(fcf_entry.get("reconciliation_tier")) == VerificationTier.DERIVED_VERIFIED.value:
                fcf_derived += 1
            elif has_reconciled_ocf and has_reconciled_capex:
                fcf_derived += 1

        return {
            "total_primary_metrics": total_primary,
            "independently_reconciled": reconciled,
            "source_linked_only": source_linked,
            "unverified": unverified,
            "failed": failed,
            "fcf_derived": fcf_derived,
            "total_periods": len(evidence_register)
        }

    @classmethod
    def get_dimension_summary(cls, results: List[ValidationResult]) -> Dict[str, Dict[str, int]]:
        summary: Dict[str, Dict[str, int]] = {}
        for r in results:
            dim = r.dimension or "STRUCTURAL"
            if dim not in summary:
                summary[dim] = {"PASS": 0, "FAIL": 0, "WARNING": 0, "UNVERIFIED": 0, "NOT_APPLICABLE": 0}
            status_key = r.status.value
            summary[dim][status_key] = summary[dim].get(status_key, 0) + 1
        return summary
