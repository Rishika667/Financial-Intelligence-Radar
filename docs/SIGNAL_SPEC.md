# Signal Specifications
**Commit**: Verified on the final phase-branch HEAD

Signals are strictly deterministic based on comparative quantitative thresholds.

- **EARNINGS_CASH_CONVERSION_DETERIORATION**: Evaluates operating cash flow vs net income.
- **FREE_CASH_FLOW_DETERIORATION**: Evaluates sequential/YoY free cash flow generation.
- **LIQUIDITY_COMPRESSION**: Evaluates short-term coverage metrics.
- **RECEIVABLES_REVENUE_DIVERGENCE**: Working-capital divergence.
- **INVENTORY_SALES_DIVERGENCE**: Inventory vs sales.
- **GROSS_MARGIN_COMPRESSION**: Evaluates gross profit margin percentage changes.

Research Mode output dynamically injects real quantitative values (e.g. `fell from 1.50x to 0.80x`) for conversion, FCF, and liquidity deterioration.
