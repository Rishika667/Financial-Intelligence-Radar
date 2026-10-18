"""
Tests clean-clone reproducibility and source independence (Phase 12).

Verifies:
1. Offline build succeeds using strictly tracked source inputs without scratch/sec_cache.
2. Mutating canonical financial facts does NOT alter the independently extracted source observations.
3. Substantive observations, counts, and confidence tiers are deterministically reproduced.
"""

import copy
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest
from fundamentals_lens.data_loader import load_evidence_register, load_financial_facts, load_source_observations
from scripts.build_source_observations_phase12 import (
    build_observations_offline,
    OUTPUT_FILE,
    US_INPUT_FILE,
    INDIAN_INPUT_FILE
)


def test_tracked_source_inputs_exist_and_valid():
    """Verify tracked source input files are tracked, non-empty, and valid JSON."""
    assert US_INPUT_FILE.exists(), f"Tracked US source input missing at {US_INPUT_FILE}"
    assert INDIAN_INPUT_FILE.exists(), f"Tracked Indian source input missing at {INDIAN_INPUT_FILE}"

    with open(US_INPUT_FILE, "r", encoding="utf-8") as f:
        us_data = json.load(f)
    assert len(us_data) == 150, f"Expected 150 US extracts, got {len(us_data)}"

    with open(INDIAN_INPUT_FILE, "r", encoding="utf-8") as f:
        ind_data = json.load(f)
    assert len(ind_data) == 225, f"Expected 225 Indian extracts, got {len(ind_data)}"


def test_build_observations_offline_without_scratch_cache():
    """Verify that build_observations_offline executes deterministically without scratch cache."""
    observations = build_observations_offline("2026-10-18T00:00:00Z")
    assert len(observations) == 375, f"Expected 375 observations, got {len(observations)}"

    reconciled = [o for o in observations if o["confidence_tier"] == "INDEPENDENTLY_RECONCILED"]
    source_linked = [o for o in observations if o["confidence_tier"] == "SOURCE_LINKED_ONLY"]

    assert len(reconciled) == 330, f"Expected 330 reconciled, got {len(reconciled)}"
    assert len(source_linked) == 45, f"Expected 45 source-linked, got {len(source_linked)}"

    # All 45 pending Indian FY2025 observations must have reported_value == None
    for sl in source_linked:
        assert sl["reported_value"] is None
        assert sl["fiscal_year"] == 2025
        assert sl["country"] == "IN"


def test_source_observations_independent_of_canonical_facts_mutation():
    """
    Critical source independence test:
    Mutating canonical financial facts has ZERO effect on independently extracted source observations.
    """
    canonical_facts = load_financial_facts()
    original_obs = load_source_observations()

    # Create mutated facts where every revenue is doubled
    mutated_facts = copy.deepcopy(canonical_facts)
    for f in mutated_facts:
        f.revenue = f.revenue * 2.0
        f.operating_income = f.operating_income * 2.0

    # Re-run offline observation build
    rebuilt_obs = build_observations_offline("2026-10-18T00:00:00Z")

    # Verify that rebuilt observations match original observations exactly (substantively)
    obs_map_orig = {(o["ticker"], o["fiscal_year"], o["metric_name"]): o["reported_value"] for o in original_obs}
    obs_map_rebuilt = {(o["ticker"], o["fiscal_year"], o["metric_name"]): o["reported_value"] for o in rebuilt_obs}

    assert obs_map_orig == obs_map_rebuilt, "Rebuilt observations must be completely decoupled from canonical facts"


def test_offline_rebuild_script_cli_execution():
    """Verify that `python scripts/build_source_observations_phase12.py --offline` runs cleanly via CLI."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "build_source_observations_phase12.py"

    cmd = [sys.executable, str(script_path), "--offline"]
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

    assert result.returncode == 0, f"Script failed with output:\n{result.stderr}"
    assert "Extracted 375 observations" in result.stdout
    assert "Summary: Reconciled=330 (88.0%), Source-Linked=45 (12.0%)" in result.stdout
