import pytest
from streamlit.testing.v1 import AppTest

def test_cwd():
    at = AppTest.from_file("../app.py", default_timeout=30)
    at.run()
    # There is os.getcwd() happening implicitly. Let's just print sys.path or os.getcwd() inside Streamlit
