# Signal specification
Ten deterministic rules, each producing severity (analyst attention priority), confidence, evidence provenance, and suppression rationale:

| Signal ID | Type | Threshold |
|-----------|------|-----------|
| RECEIVABLES_REVENUE_DIVERGENCE | Monetary divergence | ≥15% gap, ≥30% = HIGH |
| INVENTORY_SALES_DIVERGENCE | Monetary divergence | ≥15% gap, ≥30% = HIGH |
| GROSS_MARGIN_COMPRESSION | Ratio decline | ≥3pp drop, ≥6pp = HIGH |
| OPERATING_MARGIN_DETERIORATION | Ratio decline | ≥3pp drop, ≥6pp = HIGH |
| EARNINGS_CASH_CONVERSION_DETERIORATION | Ratio decline | ≥0.2 drop, ≥0.4 = HIGH |
| FREE_CASH_FLOW_DETERIORATION | Monetary decline | ≥20% of prior + \$1M floor |
| LEVERAGE_INTEREST_BURDEN | Ratio increase | ≥0.5x increase, ≥1x = HIGH |
| LIQUIDITY_COMPRESSION | Ratio decline | ≥0.1 drop, ≥0.2 = HIGH |
| SHARE_COUNT_DILUTION | Percentage increase | ≥3%, ≥10% = HIGH |
| MULTI_FACTOR_DETERIORATION_CLUSTER | 3+ simultaneous signals | Same comparison window |

Rules require comparable reported/derived inputs with strictly matching units (no cross-currency). Calculations require matching company, unit, period_end, and period_type.

Severity thresholds are deterministic and indicate analyst attention priority, not formal accounting materiality judgments.

Suppression reasons include: data quality/comparability, misaligned periods, economic insignificance.

Confidence is HIGH for all-REPORTED inputs, MEDIUM if any input is DERIVED.
