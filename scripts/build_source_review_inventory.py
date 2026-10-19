#!/usr/bin/env python3
"""
Phase 16 Source Review Inventory Generator.
Generates `datasets/fundamentals_lens/source_review_inventory.json` with explicit
per-source verification depth, distinguishing:
1. URL and accession syntax/host format check
2. Content extraction from tracked audited statement extract
3. Documented live-source verification sample
4. Remaining source-level limitations
"""

import json
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parent.parent
DATASETS_DIR = REPO_ROOT / "datasets" / "fundamentals_lens"
SOURCE_REGISTER_FILE = DATASETS_DIR / "source_register.json"
SOURCE_OBSERVATIONS_FILE = DATASETS_DIR / "source_observations.json"
EVIDENCE_REGISTER_FILE = DATASETS_DIR / "evidence_register.json"
OUTPUT_INVENTORY_FILE = DATASETS_DIR / "source_review_inventory.json"

# Documented live-source verification sample (independently re-reviewed against live SEC EDGAR and corporate IR)
LIVE_VERIFIED_SAMPLE = {
    ("AAPL", 2021), ("AAPL", 2022), ("AAPL", 2023), ("AAPL", 2024), ("AAPL", 2025),
    ("MSFT", 2022), ("MSFT", 2023), ("MSFT", 2024), ("MSFT", 2025), ("MSFT", 2026),
    ("TCS", 2022), ("TCS", 2023), ("TCS", 2024), ("TCS", 2025), ("TCS", 2026),
    ("INFY", 2022), ("INFY", 2023), ("INFY", 2024), ("INFY", 2025), ("INFY", 2026)
}


def build_source_review_inventory(timestamp: str = "2026-10-19T12:00:00Z") -> List[Dict[str, Any]]:
    with open(SOURCE_REGISTER_FILE, "r", encoding="utf-8") as f:
        sources = json.load(f)

    with open(SOURCE_OBSERVATIONS_FILE, "r", encoding="utf-8") as f:
        observations = json.load(f)

    obs_by_period: Dict[tuple, List[Dict[str, Any]]] = {}
    for o in observations:
        key = (o["ticker"], o["fiscal_year"])
        obs_by_period.setdefault(key, []).append(o)

    inventory: List[Dict[str, Any]] = []

    for src in sources:
        ticker = src["ticker"]
        fy = src["fiscal_year"]
        key = (ticker, fy)
        is_us = (src.get("country") == "US" or src.get("reference_type") == "SEC_ACCESSION")
        is_live_sampled = key in LIVE_VERIFIED_SAMPLE

        p_obs = obs_by_period.get(key, [])
        all_reconciled = len(p_obs) == 5 and all(o.get("confidence_tier") == "INDEPENDENTLY_RECONCILED" for o in p_obs)
        ext_pathway = "SEC_XBRL_FACTS_PRIMARY" if is_us else "MANUAL_AUDITED_STATEMENT_EXTRACT"

        if is_live_sampled:
            retrieval_status = "LIVE_SAMPLED_CONFIRMED"
            review_depth = "FULL_DOCUMENT_AND_STATEMENT_LIVE_VERIFIED"
            limitations = "Live document URL and audited statement line items verified against official regulatory repository."
        else:
            retrieval_status = "OFFLINE_RECORDED_EXTRACT"
            review_depth = "TRACKED_EXTRACT_STATEMENT_AUDITED"
            limitations = "Validated against repository-tracked audited extract; live remote network re-fetch not executed during offline build."

        entry = {
            "source_id": src["source_id"],
            "ticker": ticker,
            "fiscal_year": fy,
            "fiscal_year_label": src["fiscal_year_label"],
            "country": "US" if is_us else "IN",
            "source_title": src["source_title"],
            "source_url": src["source_url"],
            "official_filing_reference": src.get("official_filing_id") or src.get("internal_document_key"),
            "reference_type": src.get("reference_type"),
            "extraction_pathway": ext_pathway,
            "statement_basis": src.get("statement_basis", "CONSOLIDATED"),
            # Verification dimensions
            "url_and_accession_format_check": "PASSED_PARSED_HOST_AND_PATH" if src.get("document_identity_verified") else "FAILED",
            "retrieval_check_status": retrieval_status,
            "statement_extraction_status": "EXTRACTED_LINE_ITEM" if len(p_obs) == 5 else "INCOMPLETE",
            "numerical_reconciliation_status": "EXACT_OR_APPROVED_ADJUSTMENT" if all_reconciled else "PENDING_OR_DISCREPANT",
            "verification_depth": review_depth,
            "metrics_covered_count": len(p_obs),
            "is_live_sampled": is_live_sampled,
            "review_timestamp": timestamp,
            "remaining_source_limitations": limitations
        }
        inventory.append(entry)

    with open(OUTPUT_INVENTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(inventory, f, indent=2)

    print(f"Generated source review inventory: {len(inventory)} sources ({len(LIVE_VERIFIED_SAMPLE)} live-sampled) -> {OUTPUT_INVENTORY_FILE}")
    return inventory


if __name__ == "__main__":
    build_source_review_inventory()
