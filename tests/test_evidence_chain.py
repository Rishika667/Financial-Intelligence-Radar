import pytest
from datetime import date, datetime
from financial_radar.models import Observation, Provenance, Signal, DataQuality
from financial_radar.store import _serialize_evidence
import json

def test_evidence_serialization_preserves_contract():
    prov = Provenance(
        accession="0001-22",
        source_url="https://sec.gov/...",
        filing_date=date(2023, 1, 1),
        form="10-K",
        concept="Revenues",
        retrieval_timestamp=datetime.now(),
        raw_value=1000.0,
        mapping_version="v1",
        period_start=date(2022, 1, 1),
        fiscal_year=2022,
        fiscal_period="FY"
    )
    obs = Observation(
        company="AAPL",
        metric="revenue",
        value=1000.0,
        unit="USD",
        period_end=date(2022, 12, 31),
        period_type="ANNUAL",
        quality=DataQuality.REPORTED,
        provenance=(prov,),
        derived_from=(),
        comparable=True,
        period_start=date(2022, 1, 1),
        fiscal_year=2022,
        fiscal_period="FY"
    )
    sig = Signal(
        signal_id="TEST_SIGNAL",
        company="AAPL",
        severity="HIGH",
        confidence="HIGH",
        explanation="Test",
        evidence=(obs,)
    )

    ser = _serialize_evidence(sig.evidence)
    assert len(ser) == 1
    
    e = ser[0]
    assert e["metric"] == "revenue"
    assert e["value"] == 1000.0
    assert e["unit"] == "USD"
    assert e["period_end"] == "2022-12-31"
    assert e["period_type"] == "ANNUAL"
    assert e["quality"] == "REPORTED"
    assert e["fiscal_year"] == 2022
    assert e["fiscal_period"] == "FY"
    
    p = e["provenance"][0]
    assert p["accession"] == "0001-22"
    assert p["source_url"] == "https://sec.gov/..."
    assert p["form"] == "10-K"
    assert p["filing_date"] == "2023-01-01"
    assert p["concept"] == "Revenues"
    assert p["raw_value"] == 1000.0

def test_missing_evidence_fields_serialize_safely():
    prov = Provenance(
        accession="0001-22",
        source_url="",
        filing_date=date(2023, 1, 1),
        form="10-K",
        concept="Revenues",
        retrieval_timestamp=datetime.now(),
    )
    obs = Observation(
        company="AAPL",
        metric="revenue",
        value=None,
        unit="USD",
        period_end=date(2022, 12, 31),
        period_type="ANNUAL",
        quality=DataQuality.NOT_REPORTED,
        provenance=(prov,),
    )
    ser = _serialize_evidence([obs])
    assert ser[0]["value"] is None
    assert ser[0]["fiscal_year"] is None
    assert ser[0]["provenance"][0]["raw_value"] is None
    assert ser[0]["provenance"][0]["source_url"] == ""

def test_derived_lineage_serialization():
    obs = Observation(
        company="AAPL",
        metric="revenue",
        value=100.0,
        unit="USD",
        period_end=date(2022, 12, 31),
        period_type="QUARTER",
        quality=DataQuality.DERIVED,
        derived_from=("revenue YTD_9M", "revenue YTD_6M")
    )
    ser = _serialize_evidence([obs])
    assert ser[0]["derived_from"] == ["revenue YTD_9M", "revenue YTD_6M"]

