from financial_radar.events import extract_events


def _filing(accession="0001"):
    return {
        "accessionNumber": accession,
        "filingDate": "2025-01-15",
        "source_url": "https://sec.example/filing",
    }


def test_acquisition_detected():
    events = extract_events("ABC", _filing(), "The company completed an acquisition of XYZ Corp.")
    assert any(e["type"] == "acquisition" for e in events)


def test_multiple_events_in_one_filing():
    text = "The company announced a restructuring program and completed an acquisition."
    events = extract_events("ABC", _filing(), text)
    types = {e["type"] for e in events}
    assert "restructuring" in types
    assert "acquisition" in types


def test_empty_text_returns_nothing():
    assert extract_events("ABC", _filing(), "") == []


def test_none_text_returns_nothing():
    assert extract_events("ABC", _filing(), None) == []


def test_none_filing_returns_nothing():
    assert extract_events("ABC", None, "Some text about acquisition") == []


def test_event_id_is_deterministic():
    events1 = extract_events("ABC", _filing(), "The company completed an acquisition.")
    events2 = extract_events("ABC", _filing(), "The company completed an acquisition.")
    assert events1[0]["id"] == events2[0]["id"]


def test_different_accessions_different_ids():
    e1 = extract_events("ABC", _filing("0001"), "The company completed an acquisition.")
    e2 = extract_events("ABC", _filing("0002"), "The company completed an acquisition.")
    assert e1[0]["id"] != e2[0]["id"]


def test_all_event_types():
    texts = {
        "acquisition": "completed an acquisition",
        "divestiture": "announced a divestiture",
        "debt": "entered into a credit facility",
        "equity": "completed an equity offering",
        "buyback": "authorized a share repurchase program",
        "restructuring": "initiated a restructuring",
        "material_agreement": "entered into a material definitive agreement",
        "legal": "involved in litigation",
        "segment": "changed its reportable segment",
    }
    for expected_type, text in texts.items():
        events = extract_events("ABC", _filing(), text)
        assert any(e["type"] == expected_type for e in events), f"Failed for {expected_type}"


def test_event_snippet_has_context():
    text = "x" * 200 + "completed an acquisition" + "y" * 300
    events = extract_events("ABC", _filing(), text)
    snippet = events[0]["description"]
    assert "acquisition" in snippet
    assert len(snippet) < len(text)  # truncated


def test_event_provenance_fields():
    events = extract_events("ABC", _filing("ACC-001"), "completed an acquisition")
    e = events[0]
    assert e["company"] == "ABC"
    assert e["accession"] == "ACC-001"
    assert e["source_url"] == "https://sec.example/filing"
    assert e["filing_date"] == "2025-01-15"
