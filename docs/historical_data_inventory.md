# EyeBlackIQ — Historical Data Inventory

*Last updated: 2026-03-21*

Files found in `C:\Users\loren\Downloads\` and `C:\Users\loren\OneDrive\Desktop\NCAA Baseball\`

---

## NCAA Baseball — High Value

| File | Type | Seasons | Usable For |
|---|---|---|---|
| `2023 NCAA Division I Baseball - Iterative Strength Ratings (End of Season).csv` | ISR ratings | 2023 | Prior init |
| `2024 NCAA Division I Baseball - Iterative Strength Ratings (End of Season).csv` | ISR ratings | 2024 | Prior init |
| `2025 NCAA Division I Baseball -- Iterative Strength Ratings - Sheet1.csv` | ISR ratings | 2025 | Prior init |
| `2025 NCAA Baseball_ELO Rankings (EOY) - Sheet1.csv` | ELO ratings | 2025 | Prior ELO init |
| `2024 College Baseball Team Pitching Stats (ALL PITCHING) - Sheet1.csv` | Team pitching | 2024 | ERA baseline |
| `2024 College Baseball Team Pitching Stats (STARTING PITCHING) - Sheet1.csv` | SP stats | 2024 | SP adjustment |
| `2024 College Baseball Team Pitching Stats (BULLPEN) - Sheet1.csv` | Bullpen stats | 2024 | Relief modeling |
| `2023 NCAA ERA Stats.csv` | ERA by team | 2023 | ERA baseline |
| `2024 NCAA ERA Stats.csv` | ERA by team | 2024 | ERA baseline |
| `2025 NCAA Baseball Statistics_Team Runs - Sheet1.csv` | Team runs | 2025 | Run total model |
| `2025 NCAA Baseball Statistics_Team Runs per Game - Sheet1.csv` | R/G | 2025 | Run total model |
| `isr_2024_weekly.csv` | ISR weekly | 2024 | Backtest init |
| `isr_2026_mar9.csv` | ISR 2026 | 2026 | Current season |
| `isr_individual_rankings_2026-03-17.csv` | ISR 2026 | 2026 | Current season |
| `isr_march13_2026.csv` | ISR 2026 | 2026 | Current season |
| `03_21_2026 ELO Delta Rankings_since 3_15 - Sheet1.csv` | ELO delta | 2026 | ELO update |
| `Week6_Friday_Starters_Mar20.csv` | SP rotations | 2026 | Daily picks |
| `pitcher_era_database_week5.csv` | SP ERA | 2026 | SP adjustment |
| `ncaa_all_teams_2025_COMPLETE.csv` | Full team data | 2025 | Baseline model |
| `pitcher_rotations_d1_week1.csv` | SP rotations | 2026 | Early season |
| `friday_march13_matchups.csv` | Matchups | 2026 | Historical picks |
| `2024 NCAA OBP Stats.csv` | Batting OBP | 2024 | Batting model |
| `2024 NCAA SLG Stats.csv` | Batting SLG | 2024 | Batting model |
| `2025 NCAA Baseball Preseason Top 25 - Sheet1.csv` | Rankings | 2025 | Calibration |
| `rankings.csv` | Rankings | 2026 | Model context |

---

## Winter Baseball — Lower Priority

| File | Type | Notes |
|---|---|---|
| `winter_baseball_2024_2025_COMPLETE.csv` | Winter league | Dominican, Puerto Rico, etc. |
| `winter_leagues_batting_FINAL.csv` | Batting | Winter leagues |
| `winter_leagues_pitching_FINAL.csv` | Pitching | Winter leagues |
| `WINTER_BASEBALL_MODEL_READY.csv` | Model-ready | Already processed |
| `predictions_2025-12-21_complete.csv` | Predictions | Historical validation |
| `all_winter_predictions_20251221.csv` | Predictions | Historical validation |

---

## Other Sports (in Downloads)

| File | Type | Notes |
|---|---|---|
| `exit_velocity.csv` | Statcast | MLB exit velo data |
| `stats.csv` / `stats_2025.csv` / `stats (1).csv` | Unknown | Needs inspection |
| `time_series_validation.csv` | Validation | Backtest validation output |

---

## Files Copied to /data/historical/

Action: Key NCAA Baseball CSVs identified for copying. Run `pipeline/copy_historical.py` to execute.

**Priority files to copy:**
1. `2024 NCAA Division I Baseball - Iterative Strength Ratings (End of Season).csv` → `/data/historical/isr_ncaa_2024.csv`
2. `2025 NCAA Division I Baseball -- Iterative Strength Ratings - Sheet1.csv` → `/data/historical/isr_ncaa_2025.csv`
3. `2025 NCAA Baseball_ELO Rankings (EOY) - Sheet1.csv` → `/data/historical/elo_ncaa_2025.csv`
4. `2024 College Baseball Team Pitching Stats (ALL PITCHING) - Sheet1.csv` → `/data/historical/pitching_ncaa_2024.csv`
5. `2025 NCAA Baseball Statistics_Team Runs - Sheet1.csv` → `/data/historical/team_runs_ncaa_2025.csv`
6. `pitcher_era_database_week5.csv` → `/data/historical/pitcher_era_2026_w5.csv`

---

## What's Missing (Needed But Not Found)

- SBR historical odds for MLB, NHL (must be manually downloaded from SBR site)
- football-data.co.uk CSVs for soccer (must be downloaded from football-data.co.uk)
- MoneyPuck NHL CSVs (must be downloaded from moneypuck.com)
- Retrosheet play-by-play for MLB (must be downloaded from retrosheet.org)
