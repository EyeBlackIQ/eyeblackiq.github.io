# EyeBlackIQ — File Map

*Last updated: 2026-03-21 | Version 2.1*

---

## Root Scripts (Daily Operation)

| File | Purpose | Lines | Status |
|---|---|---|---|
| `run_morning.py` | Morning pipeline: fetch schedule → generate signals → export JSON. Entry point for daily picks. | 104 | ACTIVE |
| `run_morning_publish.py` | Post-approval publish: re-export → git push → Twitter post. Run after `approve_pod.py`. | 78 | ACTIVE |
| `run_evening.py` | Evening pipeline: grade results → update records → export JSON → git push. | 175 | ACTIVE |
| `approve_pod.py` | Human POD approval gate. Flips PENDING_APPROVAL → APPROVED in today_slip.json. | 109 | ACTIVE |

---

## Pipeline

| File | Purpose | Lines | Status |
|---|---|---|---|
| `pipeline/export.py` | Builds today_slip.json, record.json, results.json for GitHub Pages. Core export engine. | 300 | ACTIVE |
| `pipeline/grade.py` | Grades open picks against final scores. Writes results to DB. | 221 | ACTIVE |
| `pipeline/grade_mar20.py` | One-off grading script for 2026-03-20 (fixes Bug #001 POD omission). | ~50 | ARCHIVE |
| `pipeline/grade_mar20_official.py` | Alternate grading with official API validation for Mar 20. | ~60 | ARCHIVE |
| `pipeline/market_analyzer.py` | Runs on ALL signals, classifies tiers T1–T5, writes model_analyzed.json. | 176 | ACTIVE |
| `pipeline/push.py` | Git add/commit/push wrapper for docs/ and results/ directories. | 203 | ACTIVE |
| `pipeline/db_init.py` | Creates SQLite schema: signals, results, pod_records, etl_log tables. | 168 | ACTIVE |

---

## Pods (Sport Models)

| File | Purpose | Status |
|---|---|---|
| `pods/ncaa_baseball/model.py` | ELO + ISR blend model for NCAA Baseball. SP ERA adjustment. 5-gate filter. Quarter-Kelly sizing. | ACTIVE |
| `pods/mlb/model.py` | MLB model (ELO + ISR). Pitcher K props via Marcel. pybaseball integration pending. | ACTIVE (partial) |
| `pods/nhl/model.py` | NHL team ML + SOG props. MoneyPuck data integration pending. | ACTIVE (partial) |
| `pods/soccer/model.py` | Soccer 1X2 via Club Elo + xG. football-data.co.uk integration pending. | ACTIVE (partial) |
| `pods/cricket/__init__.py` | Gate-failed stub. ESPN returned 0 events, Cricinfo blocked. Forward-log strategy recommended. | DEPRECATED |
| `pods/handball/__init__.py` | Gate-failed stub. EHF requires commercial license. No public endpoint. | DEPRECATED |

### Shared Pod Utilities

| File | Purpose | Status |
|---|---|---|
| `pods/shared/gate.py` | 5-gate sequential signal filter. Any gate failure blocks the signal. | ACTIVE |
| `pods/shared/cap.py` | Quarter-Kelly sizing engine. Hard cap 3% of bankroll, daily max 15 plays. | ACTIVE |
| `pods/shared/drawdown.py` | DrawdownMonitor: kill switches (25-loss streak, 7 losing days, 3-month CLV negative). | ACTIVE |
| `pods/shared/results_store.py` | Three-file record system: model_record.json, pod_record.json, graded_slip.json. | ACTIVE |
| `pods/shared/alert_handler.py` | Kill switch alerts and notification routing. | ACTIVE |
| `pods/shared/month_context.py` | Month/season context for credibility blending (K values by games played). | ACTIVE |
| `pods/shared/tbd.py` | Placeholder for future shared utilities. | ARCHIVE |

---

## Scrapers

| File | Purpose | Status |
|---|---|---|
| `scrapers/scraper_ncaa_baseball.py` | ESPN college-baseball API: schedule, results. Props: TODO OddsAPI. | ACTIVE |
| `scrapers/scraper_mlb.py` | MLB Stats API: schedule with SP info, pitcher K stats. Props: TODO OddsAPI. | ACTIVE |
| `scrapers/scraper_nhl.py` | NHL Official API: schedule, results, player game logs. Props: TODO OddsAPI. | ACTIVE |
| `scrapers/scraper_soccer.py` | ESPN Soccer (7 leagues) + Club Elo API. Props: TODO OddsAPI. | ACTIVE |
| `scrapers/scraper_cricket.py` | Gate-failed stub with tested endpoints and forward-log path. | DEPRECATED |
| `scrapers/scraper_handball.py` | Gate-failed stub. EHF commercial license required. | DEPRECATED |
| `scrapers/fetch_lines.py` | TheRundown API wrapper for live odds including Pinnacle. | ACTIVE |
| `scrapers/fetch_odds.py` | OddsAPI wrapper. NOTE: Credits depleted — add TODO comments only, do not call. | ACTIVE (credits depleted) |

---

## Docs (GitHub Pages — Public Site)

| File | Purpose | Status |
|---|---|---|
| `docs/index.html` | Main picks page. Filter bar (sport/tier/PODs Only), On Radar section, POD badge, dark theme. | ACTIVE |
| `docs/results.html` | Full results log. Loss analysis toggle, POD sport badges, W-L-P history. | ACTIVE |
| `docs/methodology.html` | Model methodology: ELO+ISR, 5-gate filter, Kelly sizing, go-live thresholds, volume policy. | ACTIVE |
| `docs/performance.html` | Performance charts page. (Pending full chart integration.) | ACTIVE (partial) |
| `docs/style.css` | Unified CSS. Brand colors: bg=#0D0D0D, text=#F0EDE8, red=#DC143C, gold=#B8960C, blue=#4A90D9. | ACTIVE |
| `docs/data/today_slip.json` | Today's picks output. Read by index.html. Written by export.py. | ACTIVE (daily) |
| `docs/data/record.json` | Season record summary: W-L-P, net_units, ROI. Written by export.py. | ACTIVE (daily) |
| `docs/data/results.json` | Last 50 graded results. Written by export.py. Read by results.html. | ACTIVE (daily) |
| `docs/picks_today.json` | Legacy picks file. Superseded by docs/data/today_slip.json. | DEPRECATED |
| `docs/endpoint_registry.json` | All tested API endpoints with reliability scores and gate status. 14 entries. | REFERENCE |

---

## Docs (Reference — Not Published)

| File | Purpose | Status |
|---|---|---|
| `docs/audit_report.md` | Phase 4 forensic audit. P1–P5 issues logged, all P1+P2 resolved. | REFERENCE |
| `docs/bugs.md` | Full bug log. 8 bugs documented (Bugs #001–#008), all resolved. | REFERENCE |
| `docs/sport_gaps.md` | Missing data by sport. Cricket/Handball gate-failed. Soccer/NHL/MLB: downloads pending. | REFERENCE |
| `docs/historical_data_inventory.md` | 154 CSV files inventoried from Downloads. 8 key files copied to data/historical/. | REFERENCE |
| `docs/vc_analysis_mar21.md` | Investment diligence memo. 10 critical gaps, 90-day roadmap, go-live criteria. | REFERENCE |

---

## Social

| File | Purpose | Status |
|---|---|---|
| `social/twitter_post.py` | Twitter post formatter and poster. Modes: daily_picks, results. Thread support for >10 picks. | ACTIVE (keys needed) |
| `social/profile_checklist.md` | Manual Twitter profile setup checklist. Bio copy, pinned tweet, hashtag strategy. | REFERENCE |

---

## Config & Environment

| File | Purpose | Status |
|---|---|---|
| `config/.env.example` | All required env vars with empty values. Safe to commit. | ACTIVE |
| `requirements.txt` | Python dependencies. | ACTIVE |
| `README.md` | Project overview and quick-start guide. | ACTIVE |
| `README_1.md` | Legacy README from Phase 1. | ARCHIVE |
| `SETUP.md` | Phase 1 setup guide. | ARCHIVE |

---

## Data

| File/Dir | Purpose | Status |
|---|---|---|
| `data/model_analyzed.json` | All signals analyzed by market_analyzer.py (all tiers, graded flag). | ACTIVE (daily append) |
| `data/historical/` | 8 key CSV files: ISR 2023–2026, ELO 2025, pitching stats, ERA. | ACTIVE |
| `results/model_record.json` | Live season record. Written by run_evening.py. | ACTIVE |
| `results/pod_record.json` | Per-sport POD records with streak tracking. | ACTIVE |
| `results/2026-03-20_graded_slip.json` | Graded picks from Mar 20. | ARCHIVE |
| `results/2026-03-20_summary.json` | Day summary for Mar 20. | ARCHIVE |
| `pipeline/db/eyeblackiq.db` | SQLite database. Tables: signals, results, pod_records, etl_log. | ACTIVE |

---

## Key Dependencies (requirements.txt)

| Package | Used By |
|---|---|
| `requests` | All scrapers |
| `python-dotenv` | All modules (env vars) |
| `tweepy` | social/twitter_post.py |
| `tenacity` | Retry decorator on network calls |
| `tqdm` | Progress bars on long loops |

---

*All .bak and .bak2 backup files are excluded from this map. They live alongside their source files and should be removed during next cleanup pass.*
