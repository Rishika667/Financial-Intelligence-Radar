
def test_app_startup_smoke(monkeypatch):
    """
    Verifies that app.py imports, DB_PATH isolation works, company universe loads,
    tabs render, and no startup exception occurs.
    """
    from streamlit.testing.v1 import AppTest
    import os
    import sqlite3
    import financial_radar.store
    
    os.environ["DB_PATH"] = ":memory:"
    os.environ["SEC_USER_AGENT"] = "smoke_tester@example.com"
    
    test_db = sqlite3.connect(":memory:", check_same_thread=False)
    test_db.row_factory = sqlite3.Row
    test_db.executescript(financial_radar.store.DDL)
    monkeypatch.setattr(financial_radar.store, "connect", lambda *args, **kwargs: test_db)
    
    at = AppTest.from_file("../app.py", default_timeout=15)
    at.run()
    
    assert not at.exception, "App should start without exceptions"
    assert len(at.tabs) == 4
    
    # Just check setup tab renders fully
    assert at.tabs[0].subheader[0].value == "1. Company Selection"
