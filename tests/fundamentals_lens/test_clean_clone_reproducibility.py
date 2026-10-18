"""
Tests clean-clone reproducibility and source independence (Phase 13 Release Hardened).

Verifies:
1. Strict commit-only clean checkout: rebuilds cleanly from committed tree without scratch caches or working-tree diff patches.
2. Genuine source independence: mutating canonical financial facts does not alter extracted source observations;
   mutating source extracts deterministically alters observations.
3. Substantive observations, counts, and confidence tiers are deterministically reproduced.
"""

import copy
import json
import subprocess
import sys
import tempfile
import hashlib
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from fundamentals_lens.data_loader import load_evidence_register, load_financial_facts, load_source_observations
from scripts.build_source_observations_phase13 import (
    build_observations_offline,
    OUTPUT_FILE,
    US_INPUT_FILE,
    INDIAN_INPUT_FILE
)
from scripts.build_evidence_register_phase13 import build_evidence_pipeline


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


def test_genuine_source_independence_with_fact_and_extract_mutations():
    """
    Genuine source independence test:
    Part 1: Mutating canonical financial facts has ZERO effect on independently extracted source observations.
    Part 2: Mutating the source extract propagates deterministically to the observation, proving observations
            originate exclusively from the source extract and never from facts.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Baseline observations
        base_obs = build_observations_offline("2026-10-18T00:00:00Z")
        base_aapl_rev = next(o["reported_value"] for o in base_obs if o["ticker"] == "AAPL" and o["fiscal_year"] == 2021 and o["metric_name"] == "revenue")

        # Part 1: Mutate canonical facts (multiply revenue and operating income by 10)
        canonical_facts_file = REPO_ROOT / "datasets" / "fundamentals_lens" / "financial_facts_5yr.json"
        with open(canonical_facts_file, "r", encoding="utf-8") as f:
            facts_data = json.load(f)

        mutated_facts = copy.deepcopy(facts_data)
        for fact in mutated_facts:
            fact["revenue"] = fact["revenue"] * 10.0
            fact["operating_income"] = fact["operating_income"] * 10.0

        mutated_facts_file = tmp_path / "mutated_facts.json"
        with open(mutated_facts_file, "w", encoding="utf-8") as f:
            json.dump(mutated_facts, f, indent=2)

        # Run pipeline with mutated facts
        pipeline_res = build_evidence_pipeline(
            facts_file=mutated_facts_file,
            output_dir=tmp_path / "pipeline_out"
        )

        # Verify that reported values in evidence records remain 100% unchanged from baseline source extract!
        ev_flat = pipeline_res["evidence_flat_rows"]
        aapl_rev_ev = next(r for r in ev_flat if r["ticker"] == "AAPL" and r["fiscal_year"] == 2021 and r["metric_key"] == "revenue")
        assert aapl_rev_ev["reported_value"] == base_aapl_rev
        assert aapl_rev_ev["canonical_value"] == base_aapl_rev * 10.0  # Canonical took mutation, reported did not!
        assert aapl_rev_ev["reconciliation_tier"] == "DISCREPANT"  # Mismatch triggered discrepancy tier!

        # Part 2: Mutate source extract and verify observation changes deterministically
        with open(US_INPUT_FILE, "r", encoding="utf-8") as f:
            us_data = json.load(f)

        mutated_us = copy.deepcopy(us_data)
        for item in mutated_us:
            if item["ticker"] == "AAPL" and item["fiscal_year"] == 2021 and item["metric_name"] == "revenue":
                item["reported_value"] = 888888.0

        mutated_us_file = tmp_path / "mutated_us_extracts.json"
        with open(mutated_us_file, "w", encoding="utf-8") as f:
            json.dump(mutated_us, f, indent=2)

        # Rebuild observations with mutated source input
        mutated_obs = build_observations_offline("2026-10-18T00:00:00Z", us_input_file=mutated_us_file)
        mutated_aapl_rev = next(o["reported_value"] for o in mutated_obs if o["ticker"] == "AAPL" and o["fiscal_year"] == 2021 and o["metric_name"] == "revenue")
        assert mutated_aapl_rev == 888888.0, "Observation must read directly and exclusively from source extract"


def test_offline_rebuild_script_cli_execution():
    """Verify that `python scripts/build_source_observations_phase13.py --offline` runs cleanly."""
    script_path = REPO_ROOT / "scripts" / "build_source_observations_phase13.py"
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_out = Path(tmpdir) / "source_observations.json"
        cmd = [sys.executable, str(script_path), "--offline", "--output-file", str(tmp_out)]
        result = subprocess.run(cmd, cwd=str(REPO_ROOT), capture_output=True, text=True)

        assert result.returncode == 0, f"Script failed with output:\n{result.stderr}"
        assert "Extracted 375 observations" in result.stdout
        assert "Summary: Reconciled=375 (100.0%), Source-Linked=0 (0.0%)" in result.stdout
        assert tmp_out.exists()


def test_substantive_determinism():
    """Verify that two successive offline observation builds produce bit-for-bit identical outputs."""
    obs_1 = build_observations_offline("2026-10-18T12:00:00Z")
    obs_2 = build_observations_offline("2026-10-18T12:00:00Z")

    dump_1 = json.dumps(obs_1, sort_keys=True)
    dump_2 = json.dumps(obs_2, sort_keys=True)

    h1 = hashlib.sha256(dump_1.encode("utf-8")).hexdigest()
    h2 = hashlib.sha256(dump_2.encode("utf-8")).hexdigest()

    assert h1 == h2, "Offline observation builder must be strictly deterministic"


def test_isolated_clean_clone_offline_rebuild():
    """
    Demonstrates strict clean-clone reproducibility in an isolated temporary directory.
    Tests committed repository state without applying working-tree diff patches.
    Verifies that git-ignored scratch caches (e.g. scratch/sec_cache) are NOT present,
    asserts commit SHA equality between clone and parent repository,
    and ensures that the offline rebuild pipeline executes and validates with 100% passing gates.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_clone = Path(tmpdir) / "clone"
        # Perform local git clone of working directory
        res = subprocess.run(
            ["git", "clone", "--local", str(REPO_ROOT), str(tmp_clone)],
            capture_output=True,
            text=True
        )
        assert res.returncode == 0, f"Git clone failed: {res.stderr}"

        # Assert commit SHA equality between clone HEAD and source repo HEAD
        src_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT), capture_output=True, text=True).stdout.strip()
        clone_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(tmp_clone), capture_output=True, text=True).stdout.strip()
        assert clone_sha == src_sha, f"Clean clone HEAD SHA ({clone_sha}) does not match repo HEAD SHA ({src_sha})"

        # Verify scratch/sec_cache is NOT present in fresh clone
        assert not (tmp_clone / "scratch" / "sec_cache").exists()

        # Run offline source observations builder
        cmd1 = [sys.executable, str(tmp_clone / "scripts" / "build_source_observations_phase13.py"), "--offline"]
        res1 = subprocess.run(cmd1, cwd=str(tmp_clone), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res1.returncode == 0, f"Source observations rebuild failed:\n{res1.stderr}"
        assert "375 observations" in res1.stdout or "Reconciled=375" in res1.stdout

        # Run evidence register builder
        cmd2 = [sys.executable, str(tmp_clone / "scripts" / "build_evidence_register_phase13.py")]
        res2 = subprocess.run(cmd2, cwd=str(tmp_clone), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res2.returncode == 0, f"Evidence register rebuild failed:\n{res2.stderr}"
        assert "Evidence pipeline complete" in res2.stdout or "Independently reconciled:" in res2.stdout

        # Run validator
        cmd3 = [sys.executable, str(tmp_clone / "scripts" / "validate_fundamentals_data.py")]
        res3 = subprocess.run(cmd3, cwd=str(tmp_clone), capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert res3.returncode == 0, f"Validator failed in clean clone:\n{res3.stderr}"
        assert "RESULT: ALL DATA INTEGRITY GATES PASSED (100% PASS RATE)" in res3.stdout
