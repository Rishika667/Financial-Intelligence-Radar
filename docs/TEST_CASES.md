# Test cases
Executable tests cover period/FCF basics (Phase 1), all Phase 2 rule classes, SQLite watchlist and observation persistence, leverage directionality, and event classification. Tests remain unexecuted in this environment because neither python nor py is installed. Network-free fixtures are used; no SEC request occurs in unit tests.

Controls still required before production: formal SEC response fixtures for amendments/restatements, irregular fiscal calendars, complete golden rows for each rule, and Streamlit browser smoke testing.