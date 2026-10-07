# Final Release Evidence
**Time**: 2026-10-07 17:05:53 UTC
**Code SHA**: Verified on the final phase-branch HEAD
**Tests**: Verified via GitHub Actions

## Artifacts
- Legacy sqlite migration verified (schema upgrades, UNIQUE constraint rewrites, missing column filling).
- YTD selection determinism verified with reversed inputs.
- Explicit semantic ranking over pure date-fallback tested.
- `app.py` SEC Preflight explicitly checks `(USER_AGENT_CONFIGURED, SEC_REACHABLE, SUBMISSIONS_REACHABLE, XBRL_REACHABLE)`.
