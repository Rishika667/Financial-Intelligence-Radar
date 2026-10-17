import pytest
from fundamentals_lens.data_loader import load_financial_facts, load_source_register, load_companies


def test_source_register_completeness_and_uniqueness():
    sources = load_source_register()
    assert len(sources) == 75, f"Expected 75 sources, found {len(sources)}"
    
    source_ids = [s["source_id"] for s in sources]
    assert len(source_ids) == len(set(source_ids)), "All source_ids in source_register must be unique"


def test_financial_facts_to_source_provenance_linkage():
    facts = load_financial_facts()
    sources = load_source_register()
    source_map = {s["source_id"]: s for s in sources}
    
    assert len(facts) == 75, "Expected 75 financial facts"
    
    for f in facts:
        # Every fact must have a valid source_id that exists in the source register
        assert f.source_id in source_map, f"Fact {f.ticker} {f.fiscal_year} has orphan source_id: {f.source_id}"
        
        source = source_map[f.source_id]
        
        # Provenance metadata must match
        assert f.source_url == source["source_url"], f"URL mismatch for {f.ticker} {f.fiscal_year}"
        assert f.accession_id == source["accession_id"], f"Accession ID mismatch for {f.ticker} {f.fiscal_year}"
        assert f.statement_location == source["statement_location"], f"Statement location mismatch for {f.ticker} {f.fiscal_year}"
        assert f.verification_status == "VERIFIED", f"Fact {f.ticker} {f.fiscal_year} is not marked VERIFIED"


def test_source_urls_and_accession_ids_validity():
    sources = load_source_register()
    for s in sources:
        # Source URL must be a valid public HTTP/HTTPS URL
        url = s["source_url"]
        assert url.startswith("http://") or url.startswith("https://"), f"Invalid URL schema: {url}"
        assert any(d in url for d in ("sec.gov", "bseindia.com", "nseindia.com", "investor", "annualreport", ".com", ".co.in", ".in", ".org")), f"Suspicious URL: {url}"
        
        # Accession ID / filing identifier must be non-empty and non-placeholder
        accession = s["accession_id"]
        assert accession, f"Empty accession ID in source {s['source_id']}"
        assert accession.strip() != "", f"Blank accession ID in source {s['source_id']}"
        assert "TBD" not in accession and "TODO" not in accession, f"Placeholder accession ID in {s['source_id']}: {accession}"
        
        # Statement location must reference financial statements (Operations/Income, Cash Flows, etc.)
        loc = s["statement_location"]
        assert loc and len(loc) > 5, f"Invalid or too short statement location: {loc}"
        
        # Verification status
        assert s["verification_status"] == "VERIFIED"


def test_company_primary_sources():
    companies = load_companies()
    assert len(companies) == 15
    for c in companies:
        assert c.primary_source_url.startswith("http"), f"Invalid primary source URL for {c.ticker}: {c.primary_source_url}"
        if c.country == "US":
            assert c.cik and len(c.cik) == 10
            assert c.exchange in ("NASDAQ", "NYSE")
        elif c.country == "IN":
            assert c.bse_scrip or c.nse_symbol
            assert "NSE" in c.exchange or "BSE" in c.exchange
