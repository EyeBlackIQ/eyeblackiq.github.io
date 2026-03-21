# EyeBlackIQ — CHANGELOG

---

## [v0.5.1] — 2026-03-21
**Task ID:** CC-CRICKET-20260321-002 / CC-HANDBALL-20260321-002 / CC-HANDBALL-20260321-003
**Triggered by:** Master chat — Cricket ELO fix + Handball upcoming signals + Calibration
**Summary:** Three improvements: (1) Cricket ELO separated into FRANCHISE vs NATIONAL pools; (2) Handball upcoming fixtures fetcher with forward-looking signals written to DB; (3) Platt scaling calibration added to handball model with before/after backtest.

**Files Modified:**
- `scrapers/fetch_historical_cricket.py` — FRANCHISE_TEAMS set, compute_separated_elos(), run_backtest_separated(), team_type column written on every upsert
- `scrapers/fetch_handball_upcoming.py` — NEW FILE: API Sports + ESPN + hardcoded EHF CL QF fallback; generate_forward_signals()
- `pods/handball/model.py` — platt_calibrate(), run_calibration_backtest(), PLATT_SHRINK/PLATT_ENABLED constants, sys import, --calibrate CLI flag; MODEL_VERSION bumped to 1.1.0

**Schema Changes:** Yes — `cricket_team_stats.team_type TEXT DEFAULT 'NATIONAL'` column added (ALTER TABLE + new schema definition)

**Backtest Results:**
- Cricket IPL Franchise ELO: Brier=0.25519 (n=1,117 franchise matches, 18 teams)
- Cricket International ELO: Brier=0.23290 (n=3,111 national matches, 107 countries)
- Handball Calibration: Brier_raw=0.18022; Platt shrink=0.82 worsens score (-3.59 millibrier) — PLATT_ENABLED=False pending more data; overconfidence found at LOW probabilities (0-30% range), underconfidence at HIGH end (90%+)

**Handball Forward Signals:** 4 written to signals table (EHF CL QF approx dates 2026-04-02/09); pick_source=MODEL_FORWARD; no market odds — edge vs 50/50 baseline

**Backtest Impact:** Not required (improvements to existing computation, not breaking changes)
**Go-Live Parameter Changes:** No
**Tests Passed:** Yes (--elo-only, --backtest, --calibrate all ran clean)
**Pod Version:** Cricket scraper v0.5.1 | Handball model v1.1.0

---

## [v0.5.0] — 2026-03-21
**Task ID:** CC-CRICKET-20260321-001 / CC-HANDBALL-20260321-001 / CC-UI-20260321-001
**Triggered by:** Pod chat — Cricket & Handball Efficiency Notes PDF + UI bug fixes
**Summary:** Added full Cricket and Handball prediction pods (models + historical scrapers + DB schema); fixed results.html date contamination, Props/Pickems classification logic, sport filter buttons, and POD badge rendering.

**Files Modified:**
- `pods/cricket/model.py` — NEW: Resource-Value model (Par Score, Venue Z-Factor, ZIP wickets, survival probability, T20 middle-order compression, ELO + Par blend 55/45)
- `pods/handball/model.py` — NEW: Efficiency-Flow model (possession SOS, adj xG, Poisson goals, ELO + Poisson blend 55/45, usage redistribution for injuries)
- `scrapers/fetch_historical_cricket.py` — NEW: Cricsheet T20/IPL parser + API Sports fallback; 4,390 T20 matches loaded; 126 team ELOs computed; data phase cleared
- `scrapers/fetch_historical_handball.py` — NEW: API Sports EHF CL + HBL + Starligue; 973 matches; 48 team ELOs; 152 team-season stat rows; data phase cleared
- `pipeline/db_init.py` — Added 8 tables: handball_matches, handball_team_stats, handball_odds, cricket_matches, cricket_innings, cricket_team_stats, cricket_venue_stats, cricket_players (15 tables total)
- `pipeline/db_migrate.py` — NEW: Non-destructive ALTER TABLE migration for existing DBs
- `pipeline/export.py` — Edge window active (ML/Totals 3–20%, Props 3–30%, PODs bypass)
- `pipeline/grade.py` — Minor grading fixes
- `approve_pod.py` — POD approval workflow updates
- `docs/index.html` — +Cricket 🏏 +Handball 🤾 sport filters; sport icon map expanded; Props UX: T3/Scout included in main grid when Props/Pickem type filter active
- `docs/results.html` — Fix isPickem/isProp to use pick_source field; date-group headers in Daily Results (newest first, clear separator); PENDING picks dimmed 50%; renderPodBadges +CRICKET +HANDBALL; +Cricket/Handball to all sport filter bars including FMV
- `docs/style.css` — Minor style tweaks

**Schema Changes:** YES — 8 new tables added (handball + cricket). Use `pipeline/db_migrate.py` for existing DB or re-run `pipeline/db_init.py` on fresh DB.

**Backtest Impact:** N/A — new pods in data phase; no existing backtests affected

**Go-Live Parameter Changes:** No

**Tests Passed:** Yes (manual verification — 4,390 cricket matches, 973 handball matches, ELOs computed, models return DATA_PHASE=cleared)

**Pod Version:** cricket v0.1.0 | handball v0.1.0

**Master Doc Update:** Not required (pod additions within scope of existing architecture)

---

## [v0.4.0] — 2026-03-20
**Task ID:** CC-UI-20260320-001
**Summary:** Edge window activated (3–20% ML/Totals, 3–30% Props, PODs bypass), Full Market View tab added to results.html, export.py FMV output, API Sports registry.

---

## [v0.3.0] — 2026-03-19
**Task ID:** CC-UI-20260319-001
**Summary:** Pick'ems tab + Props tab source-based routing, visual flags (B2B OPP, B2B PLR, EDGE HIGH, LOW EV), POD auto-rebuild, approve_pod.py workflow.

---
