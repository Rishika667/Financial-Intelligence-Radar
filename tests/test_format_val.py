from financial_radar.synthesis import format_val

def test_synthesis_financial_formatting():
    # USD
    assert format_val(12400000000, "USD") == "$12.4B"
    assert format_val(850000000, "USD") == "$850.0M"
    assert format_val(74500, "USD") == "$74,500"
    
    # Negative USD
    assert format_val(-12400000000, "USD") == "-$12.4B"
    assert format_val(-850000000, "USD") == "-$850.0M"
    assert format_val(-74500, "USD") == "-$74,500"
    
    # Pure
    assert format_val(0.423, "pure") == "42.3%"
    assert format_val(-0.423, "pure") == "-42.3%"
    
    # Shares
    assert format_val(1500000000, "shares") == "1.5B"
