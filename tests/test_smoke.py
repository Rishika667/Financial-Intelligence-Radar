import os
import pytest
from financial_radar.core import SECClient
from financial_radar.normalization import extract_companyfacts
from financial_radar.pipeline import filing_index
@pytest.mark.skipif(os.getenv("RUN_SEC_SMOKE")!="1",reason="network smoke test is explicit and disabled in CI")
def test_real_sec_companyfacts_smoke(tmp_path):
 client=SECClient("Financial Intelligence Radar smoke-test analyst@example.com",tmp_path)
 submissions=client.submissions("0000320193"); facts=client.company_facts("0000320193")
 observations=extract_companyfacts("AAPL","0000320193",facts,filing_index(submissions,"0000320193"))
 assert observations and any(x.metric=="revenue" and x.value is not None for x in observations)