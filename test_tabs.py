import pytest
from streamlit.testing.v1 import AppTest

def test_tabs():
    at = AppTest.from_file("app.py", default_timeout=30)
    at.run()
    for i, t in enumerate(at.tabs):
        print(f"Tab {i}: {t.label}")
