import pytest
from streamlit.testing.v1 import AppTest
import os

def test_research_mode_evidence_display():
    os.environ["DB_PATH"] = "non_existent.db"
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
    
    research_tab = at.tabs[3]
    
    # Asserting UI content when DB is empty
    info_boxes = [m.value for m in research_tab.info]
    assert "No active companies." in info_boxes
