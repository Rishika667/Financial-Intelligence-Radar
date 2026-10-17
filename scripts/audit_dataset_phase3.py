import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "datasets" / "fundamentals_lens"

with open(DATA_DIR / "companies.json", encoding="utf-8") as f:
    companies = json.load(f)
with open(DATA_DIR / "financial_facts_5yr.json", encoding="utf-8") as f:
    facts = json.load(f)
with open(DATA_DIR / "source_register.json", encoding="utf-8") as f:
    sources = json.load(f)
with open(DATA_DIR / "coverage_report.json", encoding="utf-8") as f:
    coverage = json.load(f)

print(f"Total Companies: {len(companies)}")
print(f"Total Facts: {len(facts)}")
print(f"Total Sources: {len(sources)}")
print(f"Total Coverage Entries: {len(coverage)}")

companies_map = {c["ticker"]: c for c in companies}
facts_by_ticker = {}
for f in facts:
    facts_by_ticker.setdefault(f["ticker"], []).append(f)

print("\n--- COMPANY VERIFICATION SUMMARY ---")
for ticker, c_facts in sorted(facts_by_ticker.items()):
    c = companies_map[ticker]
    cov = next(x for x in coverage if x["ticker"] == ticker)
    periods = [f["fiscal_year_label"] for f in c_facts]
    print(f"{ticker:<12} | {c['country']} | {c['reporting_currency']} ({c['standard_unit_label']}) | "
          f"{len(c_facts)} periods: {periods[0]} -> {periods[-1]} | Target: {cov['target_horizon_period']} (Code {cov['target_period_status_code']})")

print("\n--- CORE METRIC DISCLOSURE AUDIT ---")
metrics = ["revenue", "operating_income", "net_income", "operating_cash_flow", "capital_expenditure"]
for m in metrics:
    valid_count = sum(1 for f in facts if f.get(m) is not None and isinstance(f[m], (int, float)))
    missing_count = sum(1 for f in facts if f.get(m) is None)
    zero_count = sum(1 for f in facts if f.get(m) == 0.0)
    print(f"  {m:<24}: {valid_count} / {len(facts)} numeric facts (Missing: {missing_count}, Zero: {zero_count})")

total_individual_values = len(facts) * len(metrics)
print(f"\nTotal Individual Reported Financial Inputs: {total_individual_values} (75 records * 5 core metrics)")

print("\n--- SOURCE REGISTER UNIQUENESS & AUDIT ---")
source_ids = [s["source_id"] for s in sources]
unique_source_ids = set(source_ids)
print(f"Unique Source IDs: {len(unique_source_ids)} / {len(source_ids)}")

fact_source_ids = {f["source_id"] for f in facts}
orphan_fact_sources = fact_source_ids - unique_source_ids
print(f"Orphan Fact Sources: {len(orphan_fact_sources)}")

# Check statement location specificity
statement_locations = [s["statement_location"] for s in sources]
generic_locations = [loc for loc in statement_locations if len(loc) < 15]
print(f"Generic / Short Statement Locations: {len(generic_locations)}")
