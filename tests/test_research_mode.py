import pytest
from streamlit.testing.v1 import AppTest

def test_research_mode_evidence_display():
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    assert not at.exception
