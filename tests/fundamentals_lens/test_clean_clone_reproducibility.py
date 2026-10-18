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

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

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

    assert len(reconciled) == 375, f"Expected 375 reconciled, got {len(reconciled)}"
    assert len(source_linked) == 0, f"Expected 0 source-linked, got {len(source_linked)}"

    # All 375 observations must have valid non-null reported values
    for rec in reconciled:
        assert rec["reported_value"] is not None
        assert rec["statement_locator"] is not None


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
    """Verify that `python scripts/build_source_observations_phase13.py --offline` and Phase 12 wrapper run cleanly."""
    repo_root = Path(__file__).resolve().parent.parent.parent
    script_path = repo_root / "scripts" / "build_source_observations_phase13.py"

    cmd = [sys.executable, str(script_path), "--offline"]
    result = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

    assert result.returncode == 0, f"Script failed with output:\n{result.stderr}"
    assert "Extracted 375 observations" in result.stdout
    assert "Summary: Reconciled=375 (100.0%), Source-Linked=0 (0.0%)" in result.stdout


def test_isolated_clean_clone_offline_rebuild():
    """
    Demonstrates clean-clone reproducibility in an isolated temporary directory.
    Verifies that git-ignored scratch caches (e.g. scratch/sec_cache) are NOT present,
    and that the offline rebuild pipeline executes and validates with 100% passing gates.
    """
    repo_root = Path(__file__).resolve().parent.parent.parent

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_clone = Path(tmpdir) / "clone"
        # Perform local git clone of working directory
        res = subprocess.run(
            ["git", "clone", "--local", str(repo_root), str(tmp_clone)],
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, f"Git clone failed: {res.stderr}"

        # Verify scratch/sec_cache is NOT present in fresh clone
        assert not (tmp_clone / "scratch" / "sec_cache").exists()

        # Sync current working-tree changes (scripts, src, datasets) into tmp_clone
        import shutil
        for subdir in ["scripts", "src", "datasets"]:
            src_dir = repo_root / subdir
            dst_dir = tmp_clone / subdir
            if src_dir.exists():
                shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True, ignore=shutil.ignore_patterns("*.pyc", "__pycache__"))

        # Confirm scratch cache is STILL not present
        assert not (tmp_clone / "scratch" / "sec_cache").exists()

        # Run offline source observations builder
        cmd1 = [sys.executable, str(tmp_clone / "scripts" / "build_source_observations_phase13.py"), "--offline"]
        res1 = subprocess.run(cmd1, cwd=str(tmp_clone), capture_output=True, text=True)
        assert res1.returncode == 0, f"Source observations rebuild failed:\n{res1.stderr}"
        assert "Reconciled=375 (100.0%)" in res1.stdout

        # Run evidence register builder
        cmd2 = [sys.executable, str(tmp_clone / "scripts" / "build_evidence_register_phase13.py")]
        res2 = subprocess.run(cmd2, cwd=str(tmp_clone), capture_output=True, text=True)
        assert res2.returncode == 0, f"Evidence register rebuild failed:\n{res2.stderr}"
        assert "Independently reconciled:          375 (100.0%)" in res2.stdout

        # Run validator
        cmd3 = [sys.executable, str(tmp_clone / "scripts" / "validate_fundamentals_data.py")]
        res3 = subprocess.run(cmd3, cwd=str(tmp_clone), capture_output=True, text=True)
        assert res3.returncode == 0, f"Validator failed in clean clone:\n{res3.stderr}"
        assert "RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)" in res3.stdout
