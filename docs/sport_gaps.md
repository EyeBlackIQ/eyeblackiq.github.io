# EyeBlackIQ — Sport Data Gaps

*Last updated: 2026-03-21*

---

## Cricket — GATE FAILED

**What was attempted:**
- ESPN Cricket scoreboard API (`site.api.espn.com/apis/site/v2/sports/cricket/wi.1/scoreboard`) — returned 0 events
- ESPN Cricinfo REST API (`hs-consumer-api.espncricinfo.com/v1/pages/matches/current`) — connection failed
- No free tier with historical match odds and results found with reliability score ≥ 6

**What exists:**
- ESPN Cricket endpoint exists but returned empty data on test date
- Cricinfo has a web interface but no documented free API with historical odds
- No free CSV equivalent of football-data.co.uk for cricket

**What's needed for backtesting gate to pass:**
- Historical results + odds (Pinnacle or Bet365 equivalent) for ≥ 3 seasons
- Minimum 500 graded matches per league
- Suggested source: CricSheet (ball-by-ball data, no odds) + separate odds scraper from OddsPortal

**Status:** PENDING — cricket pod not activated. Scraper stub only. No backtesting possible with current data access.

---

## Handball — GATE FAILED

**What was attempted:**
- EHF Champions League API (`competitionmanager.ehf.eu/api/matches`) — requires commercial license, no free tier
- ESPN Handball (`site.api.espn.com/apis/site/v2/sports/handball/all.handball/scoreboard`) — endpoint does not exist
- No free API with historical handball odds found

**What exists:**
- Handball Reference (`handball-reference.com`) has results but no free scraping API
- OddsPortal has historical handball odds but requires scraping (fragile, rate-limited)
- Bundesliga Handball has some open data at https://www.liquimoly-hbl.de/ but no machine-readable historical odds

**What's needed for backtesting gate to pass:**
- Historical results + odds for DHB-Pokal, Bundesliga, EHF Champions League
- Same minimum 500 graded matches standard
- Suggested path: OddsPortal forward-logging strategy starting now, backtest in 6+ months

**Status:** PENDING — handball pod not activated. Scraper stub only. Forward-logging strategy recommended if handball is a target market.

---

## Soccer — Partial

**What exists:**
- football-data.co.uk: results + historical odds (Pinnacle, Bet365) back to 1993 for EPL and 5 other leagues — **must be manually downloaded**
- Club Elo API: free, unlimited, back to 1939 — working
- OpenLigaDB: Bundesliga results only (no odds)
- ESPN Soccer: schedule + results only (no odds)

**Missing for full backtesting:**
- Understat xG data (requires scraping or `soccerdata` library)
- FBRef advanced stats (requires `soccerdata` library)
- Historical player-level SOT data for prop backtesting

**Status:** PARTIAL — football-data.co.uk download needed for full historical backtesting. Club Elo available now.

---

## NHL — Partial

**What exists:**
- NHL Official API: schedule, results, player stats (SOG, goals, assists) — free, unlimited
- MoneyPuck CSVs: available at `moneypuck.com/data.htm` — must be downloaded manually
- ESPN NHL: schedule + results — working

**Missing:**
- SBR historical odds (must be manually downloaded)
- Natural Stat Trick scraping (not implemented)

**Status:** PARTIAL — MoneyPuck and SBR downloads needed.

---

## MLB — Partial

**What exists:**
- MLB Stats API: official schedules, results, player stats — free, unlimited
- ESPN MLB: schedule + results — working
- Historical CSV files in Downloads: ISR, ERA, pitching stats (2023-2025)

**Missing:**
- pybaseball Statcast pulls (not yet implemented, requires `pip install pybaseball`)
- SBR historical odds (must be manually downloaded)

**Status:** PARTIAL — pybaseball installation and SBR download needed for full pipeline.
