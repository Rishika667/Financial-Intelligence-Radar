from streamlit.testing.v1 import AppTest
import pytest
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

def test_streamlit_app_workflow(tmp_path):
    os.environ["SEC_USER_AGENT"] = "Test Analyst test@example.com"
    import financial_radar.store
    financial_radar.store.DDL = financial_radar.store.DDL
    
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    
    assert not at.exception, str(at.exception)
    assert at.title[0].value == "Financial Intelligence Radar"
    
    # Portfolio Intelligence Tab
    assert at.tabs[0].subheader[0].value == "Manage Universe & Holdings"
    
    # Attention Queue Tab
    assert at.tabs[1].subheader[0].value == "Attention Queue"
    
    # Research Mode Tab
    assert at.tabs[2].selectbox[0].label == "Select Company for Research"
