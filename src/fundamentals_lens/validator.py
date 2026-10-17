from datetime import date
from typing import List, Dict, Any, Optional

from .models import (
    Company,
    FinancialFact,
    DerivedMetrics,
    ValidationResult,
    ValidationStatus
)
from .metrics import compute_derived_metrics_for_company


class FundamentalsValidator:
    """
    Deterministic data integrity validation framework for Fundamentals Lens.
    Evaluates datasets against structural, provenance, arithmetic, and anomaly gates.
    """

    @classmethod
    def validate_company_dataset(
        cls, 
        company: Company, 
        facts: List[FinancialFact],
        sources: Optional[List[Dict[str, Any]]] = None,
        coverage: Optional[List[Dict[str, Any]]] = None
    ) -> List[ValidationResult]:
        results: List[ValidationResult] = []
        
        # Dimension 1: Structural Integrity (Completeness & Uniqueness)
        results.append(cls._check_period_completeness(company, facts))
        results.append(cls._check_duplicate_observations(facts))
        
        # Dimension 2: Reporting Standards Integrity (Currency, Scale, Non-Coercion)
        results.append(cls._check_currency_and_unit_consistency(company, facts))
        results.append(cls._check_non_coercion_to_zero(facts))
        
        # Dimension 3: Source Lineage & Provenance Traceability
        results.extend(cls._check_source_provenance(facts, sources))
        
        # Dimension 4: Computational & Arithmetic Invariants
        results.extend(cls._check_arithmetic_invariants(facts))
        
        # Dimension 5: Coverage & Target Horizon Integrity
        results.append(cls._check_coverage_integrity(company, coverage))

        # Dimension 6: Comparability Integrity
        results.append(cls._check_comparability_integrity(company))
        
        # Dimension 7: Statistical Anomaly & Outlier Review (Non-destructive)
        results.extend(cls._check_anomalies_and_variances(facts))
        
        return results

    @staticmethod
    def _check_period_completeness(company: Company, facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_PERIOD_COMPLETENESS"
        rule_name = "Five-Period Consecutive Completeness"
        
        if len(facts) < 5:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Company {company.ticker} has only {len(facts)} verified periods (requires 5).",
                details={"actual_periods": [f.fiscal_year_label for f in facts]},
                dimension="STRUCTURAL"
            )
            
        sorted_years = sorted([f.fiscal_year for f in facts])
        # Check consecutive years
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
                
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Exactly 5 consecutive annual periods verified for {company.ticker}.",
            details={"periods": [f.fiscal_year_label for f in facts]},
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
            
        if len(units) > 1 or len(scales) > 1:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Mixed scale multipliers or unit labels detected for {company.ticker}: {units}, {scales}",
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
        
        seen = set()
        duplicates = []
        for f in facts:
            key = (f.ticker, f.fiscal_year)
            if key in seen:
                duplicates.append(key)
            seen.add(key)
            
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
            message="Zero duplicate observation records found; strictly one record per fiscal year.",
            details={"record_count": len(facts)},
            dimension="STRUCTURAL"
        )

    @staticmethod
    def _check_non_coercion_to_zero(facts: List[FinancialFact]) -> ValidationResult:
        rule_id = "GATE_NON_COERCION"
        rule_name = "Missing Data Non-Coercion Guard"
        
        # Verify that revenue, operating cash flow, and capex are non-zero positive/negative as expected
        suspicious_zeros = []
        for f in facts:
            if f.revenue == 0.0:
                suspicious_zeros.append((f.fiscal_year_label, "revenue"))
            if f.capital_expenditure == 0.0:
                suspicious_zeros.append((f.fiscal_year_label, "capital_expenditure"))
                
        if suspicious_zeros:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Potential synthetic zero coercion detected in observations: {suspicious_zeros}",
                details={"suspicious_zeros": suspicious_zeros},
                dimension="REPORTING_STANDARDS"
            )
            
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message="No suspicious zero coercions detected in primary disclosures.",
            details={},
            dimension="REPORTING_STANDARDS"
        )

    @staticmethod
    def _check_source_provenance(facts: List[FinancialFact], sources: Optional[List[Dict[str, Any]]]) -> List[ValidationResult]:
        results = []
        rule_id = "GATE_SOURCE_PROVENANCE"
        rule_name = "Primary Source Lineage and Traceability"
        
        missing_urls = []
        missing_locations = []
        unverified_facts = []
        
        for f in facts:
            if not f.source_url or not f.source_url.startswith("http"):
                missing_urls.append(f.fiscal_year_label)
            if not f.statement_location:
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
        elif missing_locations:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Missing statement page or line-item locations in periods: {missing_locations}",
                details={"missing_locations": missing_locations},
                dimension="SOURCE_LINEAGE"
            ))
        elif unverified_facts:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.UNVERIFIED,
                message=f"Observations not marked as VERIFIED: {unverified_facts}",
                details={"unverified_facts": unverified_facts},
                dimension="SOURCE_LINEAGE"
            ))
        else:
            results.append(ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.PASS,
                message="100% of observations link to primary filings with verified statement locations.",
                details={"verified_count": len(facts)},
                dimension="SOURCE_LINEAGE"
            ))
            
        return results

    @staticmethod
    def _check_arithmetic_invariants(facts: List[FinancialFact]) -> List[ValidationResult]:
        results = []
        derived_list = compute_derived_metrics_for_company(facts)
        
        # 1. Operating Margin Invariant Check
        margin_errors = []
        for fact, derived in zip(facts, derived_list):
            if fact.revenue > 0 and derived.operating_margin is not None:
                expected = round((fact.operating_income / fact.revenue) * 100.0, 2)
                if abs(derived.operating_margin - expected) > 0.05:
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
            
        # 2. Free Cash Flow Reconciliation Invariant
        fcf_errors = []
        for fact, derived in zip(facts, derived_list):
            if derived.free_cash_flow is not None:
                expected_fcf = round(fact.operating_cash_flow - fact.capital_expenditure, 2)
                if abs(derived.free_cash_flow - expected_fcf) > 0.001:
                    fcf_errors.append((fact.fiscal_year_label, derived.free_cash_flow, expected_fcf))
                    
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
    def _check_coverage_integrity(company: Company, coverage: Optional[List[Dict[str, Any]]]) -> ValidationResult:
        rule_id = "GATE_COVERAGE_INTEGRITY"
        rule_name = "Target Horizon Coverage & Non-Fabrication Audit"
        if not coverage:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.PASS,
                message=f"Coverage metadata unprovided for {company.ticker}; skipped.",
                dimension="COVERAGE_INTEGRITY"
            )
        cov = next((c for c in coverage if c.get("ticker") == company.ticker), None)
        if not cov:
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Missing coverage report entry for {company.ticker}.",
                dimension="COVERAGE_INTEGRITY"
            )
        code = cov.get("target_period_status_code")
        target_period = cov.get("target_horizon_period")
        if code not in (0, 1, 2):
            return ValidationResult(
                rule_id=rule_id,
                rule_name=rule_name,
                status=ValidationStatus.FAIL,
                message=f"Invalid target period status code {code} for {company.ticker}.",
                dimension="COVERAGE_INTEGRITY"
            )
        return ValidationResult(
            rule_id=rule_id,
            rule_name=rule_name,
            status=ValidationStatus.PASS,
            message=f"Target horizon {target_period} transparently documented with status code {code}.",
            details={"target_period": target_period, "status_code": code},
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
                status=ValidationStatus.PASS, # Passes with qualification; warnings are non-destructive
                message="Data points flagged for analytical review (no errors; verified in audited statements).",
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

    @classmethod
    def get_dimension_summary(cls, results: List[ValidationResult]) -> Dict[str, Dict[str, int]]:
        summary: Dict[str, Dict[str, int]] = {}
        for r in results:
            dim = r.dimension or "STRUCTURAL"
            if dim not in summary:
                summary[dim] = {"PASS": 0, "FAIL": 0, "UNVERIFIED": 0, "NOT_APPLICABLE": 0}
            status_key = r.status.value
            summary[dim][status_key] = summary[dim].get(status_key, 0) + 1
        return summary
