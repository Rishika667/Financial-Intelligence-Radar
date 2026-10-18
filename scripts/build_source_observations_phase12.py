#!/usr/bin/env python3
"""
Phase 12 / Phase 13 Independent Source Observation Pipeline Compatibility Wrapper.
Delegates to the audited Phase 13 pipeline.
"""

from scripts.build_source_observations_phase13 import (
    build_observations_offline,
    run_online_sec_audit,
    compute_file_hash,
    main,
    OUTPUT_FILE,
    BUILD_REPORT_FILE,
    US_INPUT_FILE,
    INDIAN_INPUT_FILE,
    METRIC_SORT_ORDER,
    REPO_ROOT,
    DATASETS_DIR
)

if __name__ == "__main__":
    main()
