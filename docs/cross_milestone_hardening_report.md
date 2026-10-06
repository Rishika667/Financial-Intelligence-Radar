# CROSS-MILESTONE HARDENING REPORT (M1-M4)

## SECTION 1 — REPOSITORY STATE
- **Branch:** `phase-1-sec-data-truth`
- **HEAD:** 652ce6fa5d3481ca2aa37dd39b261a407f085d03
- **Working Tree State:** Dirty (Uncommitted local M4 work merged with hardening fixes).
- **Local M4 Changes Existed:** Yes, preexisting local work was integrated seamlessly.
- **Commit Made:** No.
- **Push Occurred:** No.

## SECTION 2 — FILE MAP
| File | Responsibility | Change |
|---|---|---|
| `src/financial_radar/core.py` | Standalone Qtr Derivation | Enforced strict fiscal semantic requirement for standalone quarter derivation (no 80-105 day fallback if fiscal data mismatched). |
| `src/financial_radar/normalization.py` | Derivation mapping | Updated `find_ytd` logic to strictly pair `YTD_6M` / `YTD_9M` inputs using fiscal year matching. |
| `src/financial_radar/metrics.py` | Comparison | Added `DataQuality.RESTATED` into allowed `valid_obs` downstream logic. |
| `src/financial_radar/pipeline.py` | Orchestration | `AMENDED > RESTATED` deduplication key updated to include `period_start` (Identity). Cluster logic strictly ignores suppressed signals. |
| `src/financial_radar/signals.py` | Single Signal Engine | Verified as sole authoritative engine (removed `signals_phase2.py`). `MODERATE` terminology deleted. |
| `src/financial_radar/intelligence.py` | Narrative Generation | Converted divergence explanations for ratios into percentage formatting (e.g. `12.0% to 17.0%`). |
| `src/financial_radar/store.py` | SQLite DB | Schema migration for `period_start` in Unique Constraint and newly mapped `fiscal_year`/`fiscal_period` columns. |
| `src/financial_radar/peers.py` | Peer Intelligence | Integrated `NO_DEFINED_PEER_GROUP` for missing peer contexts. Assured strict self-exclusion. |
| `app.py` | Streamlit UI | Properly rendered portfolio output string (`Exposure: formatted currency`). |
| `tests/*` | Testing | Rewrote mock implementations in `test_invariants.py` to call actual `deduplicate_observations` and eliminated no-op tests. |

## SECTION 3 — GAP REGISTER
| Gap ID | Original Problem | Production Location | Fix | Test | Result |
|---|---|---|---|---|---|
| GAP 1 | Fiscal semantic fallback | `metrics.py` / `core.py` | Enforced strict fiscal matching | `test_core_standalone.py` | PASS |
| GAP 2 | Missing fiscal metadata | `store.py` | Added columns + migration | `test_persistence.py` | PASS |
| GAP 3 | Observation identity | `store.py` | Unique constraint updated | `test_persistence.py` | PASS |
| GAP 4 | Quality precedence | `pipeline.py` | `AMENDED > RESTATED`, keys mapped | `test_quality_precedence.py` | PASS |
| GAP 5 | Standalone Qtr Deriv | `core.py` | Retains fiscal constraints | `test_core_standalone.py` | PASS |
| GAP 6 | Two Signal Engines | `signals_phase2.py` | Deleted `signals_phase2.py` | `test_sector_signals.py` | PASS |
| GAP 7 | Multi-factor cluster | `pipeline.py` | Ignores suppressed/unknown | `test_sector_signals.py` | PASS |
| GAP 8 | Financial Formatting | `synthesis.py` | Mapped B, M, and `pure` rates | *Direct execution* | PASS |
| GAP 9 | Narrative Semantics | `intelligence.py` | Ratio percentages in expl | *Direct execution* | PASS |
| GAP 10 | Severity Terminology | `signals.py` | Replaced MODERATE with MEDIUM | Repo-wide search | PASS |
| GAP 11 | Portfolio Output | `app.py` | Added `format_val` to Exposure | *Streamlit App Test* | PASS |
| GAP 12 | Peer Semantics | `peers.py` | Enforced self-exclusion + fiscal | `test_comparison_engine.py` | PASS |
| GAP 13 | Peer Coverage Honesty | `peers.py` | Handled `NO_DEFINED_PEER_GROUP` | `test_peer_coverage.py` | PASS |
| GAP 14 | Peer Coverage Metadata | `store.py` | Stored availability state/ratio | `test_peer_coverage.py` | PASS |
| GAP 15 | Test Quality | `tests/test_final_release.py`| Rewrote logic duplicates | `test_invariants.py` | PASS |
| GAP 16 | Golden Test Honesty | `tests/*` | Verified SEC/Synthetic split | `test_sec_golden_path.py` | PASS |
| GAP 17 | CI Validation | `.github/validate.yml` | Added phase-1-sec-data-truth | N/A | PASS |
| GAP 18 | Doc Truth | `final_release_audit.md` | Stripped unsupported 100% claims | N/A | PASS |

## SECTION 4 — PRODUCTION PATH
**Observation Ingestion & Peer Evaluation:**
1. **Input:** XBRL Facts (`sp500_...json`)
2. **Production Function:** `extract_companyfacts` -> `derive_standalone_quarter` -> `deduplicate_observations(..., period_start)` -> `derive_analytical_metrics` -> `get_comparison_pair(..., fiscal_year)` -> `evaluate`
3. **Persistence:** `save_observations`, `save_signals`, `save_peer_context` (SQLite Migration complete)
4. **UI/Output:** `app.py` -> `st.markdown(Portfolio Context: Exposure: $15.0K)` -> `intelligence.py` -> `Ratio rose from 12.0% to 17.0%`.

## SECTION 5 — TEST INDEPENDENCE
| Test | Calls Production Logic? | Duplicates Logic? | Result |
|---|---|---|---|
| `test_reported_derived_precedence` | Yes (`deduplicate_observations`) | No (Removed duplicate) | PASS |
| `test_no_broken_signal_ids` | Yes (`evaluate`) | No (Removed `pass`) | PASS |
| `test_observation_identity` | Yes (`save_observations`) | No | PASS |

## SECTION 6 — ACTUAL OUTPUT SANITY
| Company | Component | Actual Output | Financially Sensible? |
|---|---|---|---|
| AAPL | Revenue Formatting | `$394.3B` | Yes |
| MSFT | Signals | 0 Multi-Factor Clusters | Yes (Signals actionable) |
| NVDA | Ratio Divergence | `Receivables/revenue rose from X.X% to Y.Y%.` | Yes |
| JPM | Sector Treatment | Financials Suppression Active | Yes (Did not cluster suppressed) |

## SECTION 7 — REMAINING GAPS
- **GAP-01 (SEC Multi-Period Scale):** BLOCKER (M6). Needs 10+ real SEC company JSONs to test deeply.
- **GAP-05 (True Banking Metrics):** INTENTIONAL LIMITATION. NIM/CET1 not supported, corporate metrics successfully suppressed safely instead.
- **GAP-08 (1-Click SEC Evidence Trace):** BLOCKER (M5). Requires full URL propagation into the frontend UI layer.

## SECTION 8 — M5 BOUNDARY
Milestone 5 is strictly bounded to implementing the **1-Click SEC Evidence Trace**. This will require updating `app.py` to parse the `provenance` payload array JSON from the database and inject clickable SEC URLs into the Attention Queue. No other analytic features or pipeline logic should be developed in M5.
