# Financial Intelligence Radar

A zero-cost, evidence-first SEC filing intelligence workflow for portfolio and research analysts.

It is **not** investment advice, a recommendation engine, price-prediction tool, or chatbot.

## Run

```bash
pip install -e '.[dev]'
streamlit run app.py
pytest -q
```

The core uses SEC public submissions and companyfacts resources, preserves retrieved JSON locally, requires a contact User-Agent, and rate-limits requests. See `docs/` for product, architecture, data and signal contracts.