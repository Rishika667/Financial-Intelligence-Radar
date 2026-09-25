# Data dictionary
Canonical observations contain: company, metric, nullable value, unit, period_end, period_type, period_start (for duration facts), data quality, comparability flag/reason, provenance chain, and derived_from lineage.

The metric layer covers: revenue, gross_profit, operating_income, net_income, operating_cash_flow, capex, accounts_receivable, inventory, cash_and_equivalents, current_liabilities, debt, share_count.

Debt is either reported directly (total debt XBRL fact) or derived from current + non-current debt when no total exists.

Data-quality states include: REPORTED, DERIVED, NOT_REPORTED, MAPPING_UNRESOLVED, CALCULATION_INVALID, COMPARABILITY_SUPPRESSED, AMENDED, RESTATED, NOT_APPLICABLE, EXTRACTION_FAILED, PERIOD_UNAVAILABLE.

Missing values never become zero. Incompatible observations (different currencies, misaligned periods) are suppressed with an explicit reason.

Observation natural identity: company + metric + period_end + period_type + unit + IFNULL(period_start, "").

Signal evidence serialization includes: metric, value, unit, period_end, period_type, quality, comparable, derived_from, period_start, and the full provenance array (accession, source_url, filing_date, form, concept, raw_value, mapping_version, period_start).
