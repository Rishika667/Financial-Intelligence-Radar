import os
import pytest
from financial_radar.core import SECClient
from financial_radar.normalization import extract_companyfacts
from financial_radar.pipeline import filing_index

@pytest.mark.skipif(os.getenv("RUN_SEC_SMOKE")!="1",reason="network smoke test is explicit and disabled in CI")
def test_real_sec_companyfacts_smoke(tmp_path):
    ua = os.environ.get("SEC_USER_AGENT")
    if not ua or "@" not in ua:
        pytest.fail("SEC_USER_AGENT environment variable is required for smoke test and must contain contact email.")
    client = SECClient(ua, tmp_path)
    submissions = client.submissions("0000320193")
    facts = client.company_facts("0000320193")
    observations = extract_companyfacts("AAPL", "0000320193", facts, filing_index(submissions, "0000320193"))
    assert observations and any(x.metric=="revenue" and x.value is not None for x in observations)