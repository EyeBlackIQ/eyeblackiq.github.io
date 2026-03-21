# EyeBlackIQ — Daily Run Guide
### Last Updated: 2026-03-21 | v0.6.0

---

## 🏃 MORNING RUN ORDER (run in this sequence)

```bash
cd C:\Users\loren\OneDrive\Desktop\eyeblackiq
```

### Step 1 — NCAA Baseball (ESPN free odds)
```bash
python pods/ncaa_baseball/model.py --date YYYY-MM-DD
```
- Pulls ESPN scoreboard + odds. Generates ELO+ISR signals.
- No API credits needed. Run first, every day.

### Step 2 — NHL Team ML + Totals (ESPN Core API)
```bash
python pods/nhl/team_ml_model.py --date YYYY-MM-DD
```
- ESPN Core API (free, no key). Pythagorean + ELO blend.
- Generates ML and totals signals.

### Step 3 — NHL Player Props (FanDuel Public API ✅ CONFIRMED WORKING)
```bash
python scrapers/scrape_fanduel_props.py --date YYYY-MM-DD
```
- **FanDuel endpoint (no key required):**
  `https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=nhl&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&includeMarkets=true`
- **Headers needed:** `User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15`
- Returns: SOG 2+/3+/4+/5+, Goals, Points, Anytime Scorer
- Cache saved to `scrapers/cache/fanduel_nhl_{date}.json`
- Also works for MLB: `customPageId=mlb`

### Step 4 — Soccer (Club Elo + ESPN)
```bash
python pods/soccer/model.py --date YYYY-MM-DD
```
- Club Elo API (free). ESPN odds (free). xG from football-data.co.uk.

### Step 5 — Handball Forward Signals (if upcoming EHF matches)
```bash
python scrapers/fetch_handball_upcoming.py
```
- Next run needed: 2026-04-01 (before Apr 2 EHF QF)
- Already has Apr 2 + Apr 9 signals in DB — DO NOT re-run until April

### Step 6 — Export to JSON (ALWAYS LAST)
```bash
python pipeline/export.py --date YYYY-MM-DD
```
- Writes `docs/data/today_slip.json` — this is what the website reads
- Also writes `record.json` and `results.json`

---

## 📊 FREE ODDS SOURCES (no API credits needed)

| Source | What it covers | Key |
|---|---|---|
| ESPN Scoreboard API | Event IDs + game structure | None |
| ESPN Core API | NHL/MLB/Soccer ML + spread + O/U | None |
| FanDuel Public API | NHL/MLB player props (SOG, Goals, Points) | None (`_ak=FhMFpcPWXMeyZxOx`) |
| Club Elo API | Soccer ELO ratings | None |
| Warren Nolan | NCAA Baseball ELO | Web scrape |
| Boyd's World | NCAA Baseball ISR | Web scrape |
| Cricsheet | Cricket T20 ball-by-ball | None |

---

## ⚠️ PAID API STATUS (as of 2026-03-21)

| API | Status | Resets |
|---|---|---|
| OddsAPI | ❌ 0/500 credits remaining | April 1 |
| TheRundown | ❌ 401 Unauthorized | April 1 (re-activate) |
| API Sports | ✅ Active (limited) | Daily reset |

---

## 🔍 SPORTSBOOK ENDPOINTS (logged for daily reuse)

### FanDuel — NHL Player Props
```
GET https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page
  ?page=CUSTOM&customPageId=nhl&pbHorizontal=false
  &_ak=FhMFpcPWXMeyZxOx&includeMarkets=true
Headers: User-Agent: Mozilla/5.0 (iPhone; CPU iPhone OS 16_0...)
```
Response: `attachments.events` (game info) + `attachments.markets` (297 markets)
Prop format: `marketName: "Player 3+ Shots on Goal"` → `runners[].runnerName` + `runners[].winRunnerOdds.americanDisplayOdds.americanOdds`

### ESPN Core API — NHL Odds
```
GET https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates=YYYYMMDD
  → event IDs

GET https://sports.core.api.espn.com/v2/sports/hockey/leagues/nhl/events/{ev_id}/competitions/{ev_id}/odds
  → ML, puck line, O/U from DraftKings
```

### ESPN Core API — NCAA Baseball
```
GET https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball/scoreboard?dates=YYYYMMDD
  → event IDs (D1 games)
```

---

## 📌 TODAY'S RUN NOTES (2026-03-21)
- FanDuel scraper confirmed working: 369 NHL prop signals
  - 24 SNIPEs (≥12% edge on SOG Poisson model)
  - 18 SLOT MACHINEs (5-12% edge)
  - 327 SCOUTs (3-5% edge)
- Forward picks in DB: 6 total (2 soccer Mar 22, 3 handball Apr 2, 1 handball Apr 9)
- Total recommended: 75 | Flagged: 319
- Export complete: 394KB today_slip.json
