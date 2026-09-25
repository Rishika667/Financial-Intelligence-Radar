    assert fcf.derived_from == ("operating_cash_flow 2025-06-30 QUARTER", "capex 2025-06-30 QUARTER")

    sig = Signal("TEST", "ABC", "LOW", "LOW", "Test", (fcf,))
    save_signals(c, [sig])
    saved = rows(c, "SELECT evidence FROM signals")[0]["evidence"]
    ev = json.loads(saved)
    assert ev[0]["derived_from"] == ["operating_cash_flow 2025-06-30 QUARTER", "capex 2025-06-30 QUARTER"]