#!/usr/bin/env python3
"""
Phase 12 / Phase 13 Evidence Register & Canonical Dataset Pipeline Compatibility Wrapper.
Delegates to the audited Phase 13 pipeline.
"""

from scripts.build_evidence_register_phase13 import (
    build_evidence_pipeline,
    derive_document_identity_verified,
    FACTS_FILE,
    SOURCES_FILE,
    EVIDENCE_JSON,
    EVIDENCE_CSV,
    DISCREPANCY_JSON,
    SOURCE_CHECK_REPORT,
    SOURCE_OBS_FILE,
    METADATA_FILE,
    COMPANIES_FILE,
    DISCREPANCIES
)

if __name__ == "__main__":
    build_evidence_pipeline()
