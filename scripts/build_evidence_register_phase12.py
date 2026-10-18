#!/usr/bin/env python3
"""
Phase 12 / Phase 13 Evidence Register & Canonical Dataset Pipeline Compatibility Wrapper.
Delegates to the audited Phase 13 pipeline.
"""

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

try:
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
except ModuleNotFoundError:
    from build_evidence_register_phase13 import (
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
