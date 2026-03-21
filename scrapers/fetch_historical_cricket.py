"""
EyeBlackIQ — scrapers/fetch_historical_cricket.py
===================================================
Fetches and stores historical cricket match data from multiple sources.

SOURCES (in priority order):
  1. Cricsheet         — FREE ball-by-ball + match CSV (direct download, no key)
     https://cricsheet.org/downloads/{format}.csv.zip
     Formats: t20s, odis (IPL included, ICC events included)
  2. API Sports        — historical fixtures by league/season (key: APISPORTS_KEY)
  3. Kaggle            — ODI cricket dataset (requires KAGGLE_KEY)
  4. OddsPortal        — historical match winner odds (best-effort, no Selenium)

OUTPUT TABLES:
  - cricket_matches       : match-level results
  - cricket_innings       : innings-level scores
  - cricket_team_stats    : ELO + batting/bowling averages (computed)
  - cricket_venue_stats   : venue scoring averages (Z-Factor data)
  - cricket_players       : player batting stats (for prop projections)

CRICSHEET DATA (free, comprehensive):
  - t20s.csv.zip: ALL international + franchise T20 matches (IPL, Big Bash, etc.)
  - odis.csv.zip: ALL ODI matches
  - Columns: match_id, date, venue, team1, team2, toss_winner, toss_decision,
             winner, winner_runs, winner_wickets, player_of_match, etc.

USAGE:
  python scrapers/fetch_historical_cricket.py --format T20
  python scrapers/fetch_historical_cricket.py --format T20 --source cricsheet
  python scrapers/fetch_historical_cricket.py --elo-only
  python scrapers/fetch_historical_cricket.py --status

NOTE: Walk-forward backtest requires >= 150 T20 matches.
      Cricsheet T20 data alone provides 1000s of matches — more than sufficient.
"""

import os
import sys
import csv
import json
import time
import math
import io
import zipfile
import sqlite3
import argparse
import logging
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

LOG_PATH = Path(__file__).parent.parent / "logs" / "scraper_errors.log"
LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(LOG_PATH, encoding="utf-8"),
    ],
)
logger = logging.getLogger("fetch_historical_cricket")

BASE_DIR = Path(__file__).parent.parent
DB_PATH  = BASE_DIR / "pipeline" / "db" / "eyeblackiq.db"
DATA_DIR = BASE_DIR / "data" / "cricket"
DATA_DIR.mkdir(parents=True, exist_ok=True)

# API Sports
APISPORTS_BASE    = "https://v1.cricket.api-sports.io"
APISPORTS_KEY     = os.getenv("APISPORTS_KEY", "")

# Cricsheet download URLs
CRICSHEET_BASE    = "https://cricsheet.org/downloads"
CRICSHEET_URLS    = {
    "T20":  f"{CRICSHEET_BASE}/t20s_male_csv2.zip",
    "ODI":  f"{CRICSHEET_BASE}/odis_male_csv2.zip",
}
CRICSHEET_IPL_URL = f"{CRICSHEET_BASE}/ipl_male_csv2.zip"

# Target leagues for API Sports
API_LEAGUES = {
    1:   "IPL",
    9:   "ICC T20 World Cup",
    10:  "ICC ODI World Cup",
    2:   "The Hundred",
    167: "Big Bash League",
    44:  "CPL",
}

DEFAULT_SEASONS = [2021, 2022, 2023, 2024]

# ELO calibration
ELO_DEFAULT = 1500
ELO_K       = 20
ELO_K_EARLY = 32

# ── Franchise / National team separation ─────────────────────────────────────
# All known IPL franchise team names (historical + current).
# FRANCHISE teams compete only in IPL bracket.
# NATIONAL teams compete in ICC / bilateral internationals.
FRANCHISE_TEAMS: set = {
    "Mumbai Indians",
    "Chennai Super Kings",
    "Royal Challengers Bangalore",
    "Royal Challengers Bengaluru",   # renamed 2024
    "Kolkata Knight Riders",
    "Delhi Capitals",
    "Delhi Daredevils",              # pre-2019 name
    "Rajasthan Royals",
    "Sunrisers Hyderabad",
    "Punjab Kings",
    "Kings XI Punjab",               # pre-2021 name
    "Gujarat Titans",
    "Lucknow Super Giants",
    "Kochi Tuskers Kerala",          # 2011 defunct
    "Rising Pune Supergiant",        # 2016-17 defunct
    "Rising Pune Supergiants",
    "Pune Warriors",                 # 2011-13 defunct
    "Deccan Chargers",               # 2008-12 defunct
}

# League names that are exclusively IPL franchise competitions
IPL_LEAGUE_KEYWORDS = {"IPL", "INDIAN PREMIER LEAGUE"}

# League names that are exclusively international (national teams) competitions
INTERNATIONAL_LEAGUE_KEYWORDS = {
    "T20 INTERNATIONAL",
    "T20 WORLD CUP",
    "WORLD T20",
    "ICC",
    "BILATERAL",
    "INTERNATIONAL",
}


def get_team_type(team_name: str) -> str:
    """
    Classify a team as 'FRANCHISE' (IPL club) or 'NATIONAL' (country team).
    Checks exact membership in FRANCHISE_TEAMS set.
    """
    return "FRANCHISE" if team_name in FRANCHISE_TEAMS else "NATIONAL"


def is_ipl_match(league_name: str, home_team: str, away_team: str) -> bool:
    """
    Return True if this match is an IPL franchise match.
    Criteria: league_name contains 'IPL' OR both teams are franchises.
    """
    league_upper = (league_name or "").upper()
    if any(kw in league_upper for kw in IPL_LEAGUE_KEYWORDS):
        return True
    # Fallback: both teams are known franchises
    return (home_team in FRANCHISE_TEAMS) and (away_team in FRANCHISE_TEAMS)


def is_international_match(league_name: str, home_team: str, away_team: str) -> bool:
    """
    Return True if this match is an international (national team) match.
    A match is international if NEITHER team is a franchise.
    """
    return (home_team not in FRANCHISE_TEAMS) and (away_team not in FRANCHISE_TEAMS)

# T20 format defaults
T20_LG_AVG   = 165.0
T20_LG_STD   = 22.0
T20_BOWL_RPO = 8.25   # runs per over (league bowling average)


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    """Create cricket-specific tables if they don't exist."""
    schema = """
    CREATE TABLE IF NOT EXISTS cricket_matches (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id       TEXT UNIQUE,
        date             TEXT NOT NULL,
        league_id        INTEGER,
        league_name      TEXT,
        format           TEXT NOT NULL DEFAULT 'T20',
        season           TEXT,
        home_team        TEXT NOT NULL,
        away_team        TEXT NOT NULL,
        home_score       INTEGER,
        away_score       INTEGER,
        venue            TEXT,
        toss_winner      TEXT,
        toss_decision    TEXT,
        result           TEXT,
        winner           TEXT,
        margin_runs      INTEGER,
        margin_wickets   INTEGER,
        home_odds        REAL,
        away_odds        REAL,
        total_line       REAL,
        over_odds        REAL,
        under_odds       REAL,
        game_time        TEXT,
        status           TEXT DEFAULT 'FT',
        source           TEXT DEFAULT 'CRICSHEET',
        created_at       TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS cricket_innings (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        fixture_id       TEXT,
        innings_number   INTEGER,
        batting_team     TEXT,
        bowling_team     TEXT,
        runs             INTEGER,
        wickets          INTEGER,
        overs            REAL,
        extras           INTEGER,
        run_rate         REAL,
        source           TEXT DEFAULT 'CRICSHEET'
    );

    CREATE TABLE IF NOT EXISTS cricket_team_stats (
        id                          INTEGER PRIMARY KEY AUTOINCREMENT,
        season                      TEXT NOT NULL,
        league_id                   INTEGER DEFAULT 0,
        format                      TEXT NOT NULL DEFAULT 'T20',
        team_name                   TEXT NOT NULL,
        team_type                   TEXT NOT NULL DEFAULT 'NATIONAL',
        games_played                INTEGER DEFAULT 0,
        wins                        INTEGER DEFAULT 0,
        losses                      INTEGER DEFAULT 0,
        avg_score_batting_first     REAL DEFAULT 165.0,
        avg_score_batting_second    REAL DEFAULT 155.0,
        avg_runs_conceded           REAL DEFAULT 165.0,
        win_pct_batting_first       REAL DEFAULT 0.5,
        win_pct_batting_second      REAL DEFAULT 0.5,
        toss_win_pct                REAL DEFAULT 0.5,
        elo_rating                  REAL DEFAULT 1500,
        last_updated                TEXT,
        UNIQUE(season, league_id, format, team_name)
    );

    CREATE TABLE IF NOT EXISTS cricket_venue_stats (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        venue                   TEXT UNIQUE,
        format                  TEXT DEFAULT 'T20',
        avg_first_innings_score REAL DEFAULT 165.0,
        std_first_innings_score REAL DEFAULT 22.0,
        avg_total_runs          REAL DEFAULT 330.0,
        matches_played          INTEGER DEFAULT 0,
        pace_friendly           REAL DEFAULT 0.5,
        boundary_percentage     REAL DEFAULT 0.0,
        last_updated            TEXT
    );

    CREATE TABLE IF NOT EXISTS cricket_players (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        player_name         TEXT NOT NULL,
        team                TEXT,
        season              TEXT,
        format              TEXT DEFAULT 'T20',
        matches             INTEGER DEFAULT 0,
        innings             INTEGER DEFAULT 0,
        runs_total          INTEGER DEFAULT 0,
        avg_runs            REAL DEFAULT 0,
        strike_rate         REAL DEFAULT 0,
        batting_position    INTEGER DEFAULT 5,
        balls_faced_avg     REAL DEFAULT 15,
        wicket_rate         REAL DEFAULT 0.045,
        last_updated        TEXT,
        UNIQUE(player_name, team, season, format)
    );

    CREATE INDEX IF NOT EXISTS idx_cm_date    ON cricket_matches(date, format);
    CREATE INDEX IF NOT EXISTS idx_cm_teams   ON cricket_matches(home_team, away_team);
    CREATE INDEX IF NOT EXISTS idx_cts_team   ON cricket_team_stats(team_name, format, season);
    CREATE INDEX IF NOT EXISTS idx_cvs_venue  ON cricket_venue_stats(venue);
    """
    with get_conn() as conn:
        conn.executescript(schema)
        conn.commit()
    logger.info("[CRICKET] Tables ensured.")


# ── Cricsheet downloader ───────────────────────────────────────────────────────
def download_cricsheet(format_str: str = "T20", ipl_only: bool = False) -> int:
    """
    Download and parse Cricsheet CSV data for the given format.
    Cricsheet is FREE — no API key required.
    Returns number of matches stored.

    Cricsheet CSV format (csv2 format):
      match_id, season, start_date, venue, innings, batting_team, bowling_team, ...
      The data is ball-by-ball, so we aggregate to match level.

    The match-info file structure varies. We use the "all-matches" CSV which
    has one row per match with key match metadata.
    """
    url = CRICSHEET_IPL_URL if ipl_only else CRICSHEET_URLS.get(format_str, CRICSHEET_URLS["T20"])
    fmt_label = "IPL" if ipl_only else format_str

    cache_path = DATA_DIR / f"cricsheet_{fmt_label.lower()}.zip"
    csv_dir    = DATA_DIR / f"cricsheet_{fmt_label.lower()}"
    csv_dir.mkdir(exist_ok=True)

    # Download if not cached
    if not cache_path.exists():
        logger.info(f"[CRICSHEET] Downloading {fmt_label} data from {url}...")
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EyeBlackIQ/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
            with open(cache_path, "wb") as f:
                f.write(data)
            logger.info(f"[CRICSHEET] Downloaded {len(data):,} bytes → {cache_path.name}")
        except Exception as e:
            logger.error(f"[CRICSHEET] Download failed: {e}")
            return 0
    else:
        logger.info(f"[CRICSHEET] Using cached: {cache_path.name}")

    # Extract
    try:
        with zipfile.ZipFile(cache_path, "r") as zf:
            names = zf.namelist()
            logger.info(f"[CRICSHEET] Zip contains {len(names)} files.")

            # Look for the all-matches summary CSV (varies by format)
            summary_files = [n for n in names if "_info" not in n and n.endswith(".csv") and "README" not in n.upper()]
            if not summary_files:
                summary_files = [n for n in names if n.endswith(".csv")]

            total_stored = 0
            for fname in summary_files[:1]:   # use first match-level CSV
                with zf.open(fname) as f:
                    content = f.read().decode("utf-8", errors="replace")

                reader = csv.DictReader(io.StringIO(content))
                rows   = list(reader)
                logger.info(f"[CRICSHEET] Parsing {fname}: {len(rows)} rows, cols={reader.fieldnames[:8] if reader.fieldnames else '?'}")

                matches_to_store = []
                for row in rows:
                    # Cricsheet column names vary slightly — try multiple aliases
                    date_val  = row.get("start_date") or row.get("date") or ""
                    venue_val = row.get("venue") or ""
                    team1     = row.get("team1") or row.get("home_team") or ""
                    team2     = row.get("team2") or row.get("away_team") or ""
                    winner    = row.get("winner") or ""
                    season    = row.get("season") or date_val[:4]
                    mid       = row.get("match_id") or row.get("id") or f"CS_{date_val}_{team1[:3]}_{team2[:3]}"
                    toss_w    = row.get("toss_winner") or ""
                    toss_dec  = row.get("toss_decision") or ""
                    event     = row.get("event") or row.get("competition") or row.get("competition_stage") or ""
                    margin_r  = row.get("winner_runs")
                    margin_w  = row.get("winner_wickets")

                    # Determine home/away from fixture data or use alphabetical
                    home_team = team1
                    away_team = team2

                    matches_to_store.append({
                        "fixture_id":      str(mid),
                        "date":            date_val[:10],
                        "league_id":       1 if "IPL" in event.upper() else 0,
                        "league_name":     event or fmt_label,
                        "format":          format_str,
                        "season":          str(season),
                        "home_team":       home_team,
                        "away_team":       away_team,
                        "venue":           venue_val,
                        "toss_winner":     toss_w,
                        "toss_decision":   toss_dec,
                        "winner":          winner,
                        "margin_runs":     int(margin_r) if str(margin_r or "").isdigit() else None,
                        "margin_wickets":  int(margin_w) if str(margin_w or "").isdigit() else None,
                        "result":          "home_win" if winner == home_team else ("away_win" if winner == away_team else "no_result"),
                        "status":          "FT",
                        "source":          "CRICSHEET",
                    })

                stored = _store_cricket_matches(matches_to_store)
                total_stored += stored
                logger.info(f"[CRICSHEET] Stored {stored} new matches from {fname}.")

    except zipfile.BadZipFile as e:
        logger.error(f"[CRICSHEET] Bad zip file: {e}")
        return 0

    return total_stored


def _store_cricket_matches(matches: list) -> int:
    """Bulk insert cricket matches. Returns number of new rows."""
    if not matches:
        return 0
    inserted = 0
    with get_conn() as conn:
        for m in matches:
            if not m.get("home_team") or not m.get("date"):
                continue
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO cricket_matches
                       (fixture_id, date, league_id, league_name, format, season,
                        home_team, away_team, venue, toss_winner, toss_decision,
                        winner, margin_runs, margin_wickets, result, status, source)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        m["fixture_id"], m["date"], m.get("league_id", 0), m.get("league_name",""),
                        m["format"], m.get("season",""), m["home_team"], m["away_team"],
                        m.get("venue",""), m.get("toss_winner",""), m.get("toss_decision",""),
                        m.get("winner",""), m.get("margin_runs"), m.get("margin_wickets"),
                        m.get("result",""), m.get("status","FT"), m.get("source","CRICSHEET"),
                    )
                )
                if conn.execute("SELECT changes()").fetchone()[0]:
                    inserted += 1
            except sqlite3.IntegrityError:
                pass
        conn.commit()

    # ETL log
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO etl_log (source, table_name, rows_loaded, as_of_ts, run_ts) VALUES (?,?,?,?,?)",
            ("CRICSHEET", "cricket_matches", inserted,
             datetime.now(timezone.utc).strftime("%Y-%m-%d"),
             datetime.now(timezone.utc).isoformat())
        )
        conn.commit()

    return inserted


# ── API Sports fallback ────────────────────────────────────────────────────────
def fetch_apisports_cricket(league_id: int, season: int, format_str: str = "T20") -> int:
    """Fetch cricket fixtures from API Sports for a league/season."""
    if not APISPORTS_KEY:
        return 0

    url = f"{APISPORTS_BASE}/fixtures?league={league_id}&season={season}"
    req = urllib.request.Request(url)
    req.add_header("x-rapidapi-key",  APISPORTS_KEY)
    req.add_header("x-apisports-key", APISPORTS_KEY)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        time.sleep(0.7)
    except Exception as e:
        logger.error(f"  API Sports cricket error L={league_id} S={season}: {e}")
        return 0

    matches = []
    for item in (data.get("response") or []):
        f = item.get("fixture") or item
        teams  = item.get("teams") or {}
        scores = item.get("scores") or item.get("score") or {}

        ht = (teams.get("home") or {}).get("name")
        at = (teams.get("away") or {}).get("name")
        if not ht or not at:
            continue

        matches.append({
            "fixture_id":  str(f.get("id") or f"API_{league_id}_{season}_{len(matches)}"),
            "date":        ((f.get("date") or "")[:10]),
            "league_id":   league_id,
            "league_name": API_LEAGUES.get(league_id, f"L{league_id}"),
            "format":      format_str,
            "season":      str(season),
            "home_team":   ht,
            "away_team":   at,
            "home_score":  (scores.get("home") or {}).get("total") if isinstance(scores.get("home"), dict) else None,
            "away_score":  (scores.get("away") or {}).get("total") if isinstance(scores.get("away"), dict) else None,
            "status":      (f.get("status") or {}).get("short") or "FT",
            "source":      "API_SPORTS",
        })

    stored = _store_cricket_matches(matches)
    logger.info(f"  API Sports: {len(matches)} fixtures, {stored} new — L={league_id} S={season}")
    return stored


# ── ELO computation ────────────────────────────────────────────────────────────
def compute_elo_from_matches(format_str: str = "T20") -> dict:
    """
    DEPRECATED wrapper — use compute_separated_elos() for the canonical split.
    Returns a merged dict (franchise_elo | national_elo) for backward compatibility.
    """
    result = compute_separated_elos(format_str)
    merged = {}
    merged.update(result["national"])
    merged.update(result["franchise"])
    return merged


def compute_separated_elos(format_str: str = "T20") -> dict:
    """
    Compute ELO ratings with strict FRANCHISE vs NATIONAL separation.

    - IPL matches (both teams are FRANCHISE) → update franchise ELO pool only.
    - International matches (both teams are NATIONAL) → update national ELO pool only.
    - Mixed matches (one franchise, one national — should not exist) → skipped.

    Returns:
        {
          "franchise": {team_name: elo_float, ...},   # IPL club ELOs
          "national":  {team_name: elo_float, ...},   # Country ELOs
        }
    """
    HFA = 35  # Cricket home advantage

    try:
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT date, league_name, home_team, away_team, winner, result
                   FROM cricket_matches
                   WHERE format = ? AND status IN ('FT','FINISHED','COMPLETE')
                     AND home_team IS NOT NULL AND away_team IS NOT NULL
                   ORDER BY date ASC""",
                (format_str,)
            ).fetchall()
    except sqlite3.OperationalError:
        return {"franchise": {}, "national": {}}

    franchise_elo  = {}
    national_elo   = {}
    franchise_gc   = {}   # game count per team for K-factor selection
    national_gc    = {}

    ipl_count = 0
    intl_count = 0
    skipped    = 0

    for row in rows:
        ht     = row["home_team"]
        at     = row["away_team"]
        winner = row["winner"]  if row["winner"]  is not None else ""
        league = row["league_name"] if row["league_name"] is not None else ""

        ht_is_franchise = ht in FRANCHISE_TEAMS
        at_is_franchise = at in FRANCHISE_TEAMS

        # Route the match to the correct ELO pool
        if ht_is_franchise and at_is_franchise:
            # IPL franchise match
            elo_pool = franchise_elo
            gc_pool  = franchise_gc
            ipl_count += 1
        elif (not ht_is_franchise) and (not at_is_franchise):
            # National/international match
            elo_pool = national_elo
            gc_pool  = national_gc
            intl_count += 1
        else:
            # Mixed — skip (logically shouldn't happen with clean data)
            skipped += 1
            continue

        elo_pool.setdefault(ht, ELO_DEFAULT)
        elo_pool.setdefault(at, ELO_DEFAULT)
        gc_pool.setdefault(ht, 0)
        gc_pool.setdefault(at, 0)

        e_h = 1 / (1 + 10 ** (-((elo_pool[ht] + HFA) - elo_pool[at]) / 400))
        e_a = 1 - e_h

        if winner == ht:
            s_h, s_a = 1.0, 0.0
        elif winner == at:
            s_h, s_a = 0.0, 1.0
        else:
            s_h, s_a = 0.5, 0.5  # no result / tie / superover

        k_h = ELO_K_EARLY if gc_pool[ht] < 20 else ELO_K
        k_a = ELO_K_EARLY if gc_pool[at] < 20 else ELO_K

        elo_pool[ht] = elo_pool[ht] + k_h * (s_h - e_h)
        elo_pool[at] = elo_pool[at] + k_a * (s_a - e_a)
        gc_pool[ht] += 1
        gc_pool[at] += 1

    logger.info(
        f"[ELO/CRICKET/{format_str}] Separated ELO computation complete — "
        f"IPL={ipl_count} matches ({len(franchise_elo)} franchises), "
        f"International={intl_count} matches ({len(national_elo)} national teams), "
        f"Skipped={skipped}"
    )
    return {"franchise": franchise_elo, "national": national_elo}


def compute_venue_stats(format_str: str = "T20") -> int:
    """
    Aggregate venue stats from cricket_innings (if available) or
    estimate from cricket_matches scores.
    Writes to cricket_venue_stats.
    """
    now = datetime.now(timezone.utc).isoformat()

    # Try innings table first
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT cm.venue, ci.runs, ci.innings_number
                   FROM cricket_innings ci
                   JOIN cricket_matches cm ON cm.fixture_id = ci.fixture_id
                   WHERE cm.format = ? AND ci.innings_number = 1 AND ci.runs IS NOT NULL""",
                (format_str,)
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    # Fallback: estimate from home_score as first innings proxy
    if not rows:
        try:
            with get_conn() as conn:
                rows = conn.execute(
                    """SELECT venue, home_score as runs, 1 as innings_number
                       FROM cricket_matches
                       WHERE format = ? AND home_score IS NOT NULL AND venue != ''""",
                    (format_str,)
                ).fetchall()
        except sqlite3.OperationalError:
            return 0

    # Aggregate by venue
    venue_runs = {}
    for row in rows:
        v = row["venue"]
        if not v:
            continue
        venue_runs.setdefault(v, [])
        if row["runs"] is not None:
            venue_runs[v].append(float(row["runs"]))

    upserted = 0
    with get_conn() as conn:
        for venue, run_list in venue_runs.items():
            if len(run_list) < 5:
                continue  # need minimum sample
            avg = sum(run_list) / len(run_list)
            variance = sum((r - avg)**2 for r in run_list) / len(run_list)
            std = math.sqrt(variance)
            conn.execute(
                """INSERT INTO cricket_venue_stats
                   (venue, format, avg_first_innings_score, std_first_innings_score,
                    avg_total_runs, matches_played, last_updated)
                   VALUES (?,?,?,?,?,?,?)
                   ON CONFLICT(venue) DO UPDATE SET
                     avg_first_innings_score=excluded.avg_first_innings_score,
                     std_first_innings_score=excluded.std_first_innings_score,
                     avg_total_runs=excluded.avg_total_runs,
                     matches_played=excluded.matches_played,
                     last_updated=excluded.last_updated""",
                (venue, format_str, round(avg, 1), round(std, 1),
                 round(avg * 1.95, 1), len(run_list), now)
            )
            upserted += 1
        conn.commit()

    logger.info(f"[CRICKET] Venue stats: {upserted} venues computed.")
    return upserted


def compute_team_stats(format_str: str = "T20") -> int:
    """
    Aggregate team batting/bowling averages from match history.
    Writes to cricket_team_stats.
    """
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT season, league_id, home_team, away_team, home_score,
                          away_score, toss_winner, winner
                   FROM cricket_matches
                   WHERE format = ? AND status IN ('FT','FINISHED','COMPLETE')
                     AND home_team IS NOT NULL AND away_team IS NOT NULL""",
                (format_str,)
            ).fetchall()
    except sqlite3.OperationalError:
        return 0

    stats = {}

    def _init(k):
        stats[k] = {
            "gp":0, "wins":0, "losses":0,
            "bat_first_scores":[], "bat_second_scores":[],
            "runs_conceded":[], "bat_first_wins":0, "bat_first_gp":0,
            "bat_second_wins":0, "bat_second_gp":0,
            "toss_wins":0, "toss_gp":0,
        }

    for row in rows:
        season  = row["season"] or "ALL"
        lid     = row["league_id"] or 0
        ht, at  = row["home_team"], row["away_team"]
        hs, as_ = row["home_score"], row["away_score"]
        winner  = row["winner"]  or "" if row["winner"]  is not None else ""
        toss_w  = row["toss_winner"] or "" if row["toss_winner"] is not None else ""

        for team, scored, conceded, bats_first in [
            (ht, hs, as_, True),
            (at, as_, hs, False),
        ]:
            if not team:
                continue
            k = (season, lid, team)
            if k not in stats:
                _init(k)
            s = stats[k]
            s["gp"] += 1
            won = (winner == team)
            if won:   s["wins"]   += 1
            else:     s["losses"] += 1
            if toss_w == team:
                s["toss_wins"] += 1
            s["toss_gp"] += 1

            if scored is not None:
                if bats_first:
                    s["bat_first_scores"].append(scored)
                    s["bat_first_gp"] += 1
                    if won:  s["bat_first_wins"] += 1
                else:
                    s["bat_second_scores"].append(scored)
                    s["bat_second_gp"] += 1
                    if won:  s["bat_second_wins"] += 1
            if conceded is not None:
                s["runs_conceded"].append(conceded)

    # Use separated ELO pools — franchise teams get their IPL ELO,
    # national teams get their international ELO.
    elo_pools = compute_separated_elos(format_str)
    franchise_elo_map = elo_pools["franchise"]
    national_elo_map  = elo_pools["national"]
    now = datetime.now(timezone.utc).isoformat()

    upserted = 0
    with get_conn() as conn:
        # Ensure team_type column exists (idempotent migration)
        existing_cols = [r[1] for r in conn.execute("PRAGMA table_info(cricket_team_stats)").fetchall()]
        if "team_type" not in existing_cols:
            conn.execute("ALTER TABLE cricket_team_stats ADD COLUMN team_type TEXT DEFAULT 'NATIONAL'")
            conn.commit()

        for (season, lid, team), s in stats.items():
            gp = s["gp"]
            if gp == 0:
                continue
            avg_bat1 = sum(s["bat_first_scores"])  / len(s["bat_first_scores"])  if s["bat_first_scores"]  else T20_LG_AVG
            avg_bat2 = sum(s["bat_second_scores"]) / len(s["bat_second_scores"]) if s["bat_second_scores"] else T20_LG_AVG * 0.94
            avg_conc = sum(s["runs_conceded"])      / len(s["runs_conceded"])     if s["runs_conceded"]     else T20_LG_AVG
            wp_bat1  = s["bat_first_wins"]  / s["bat_first_gp"]  if s["bat_first_gp"]  else 0.5
            wp_bat2  = s["bat_second_wins"] / s["bat_second_gp"] if s["bat_second_gp"] else 0.5
            toss_pct = s["toss_wins"] / s["toss_gp"]             if s["toss_gp"]        else 0.5

            # Determine team_type and select the correct ELO pool
            t_type = get_team_type(team)
            if t_type == "FRANCHISE":
                team_elo = franchise_elo_map.get(team, ELO_DEFAULT)
            else:
                team_elo = national_elo_map.get(team, ELO_DEFAULT)

            conn.execute(
                """INSERT INTO cricket_team_stats
                   (season, league_id, format, team_name, team_type, games_played, wins, losses,
                    avg_score_batting_first, avg_score_batting_second, avg_runs_conceded,
                    win_pct_batting_first, win_pct_batting_second, toss_win_pct,
                    elo_rating, last_updated)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(season, league_id, format, team_name) DO UPDATE SET
                     team_type=excluded.team_type,
                     games_played=excluded.games_played,
                     wins=excluded.wins, losses=excluded.losses,
                     avg_score_batting_first=excluded.avg_score_batting_first,
                     avg_score_batting_second=excluded.avg_score_batting_second,
                     avg_runs_conceded=excluded.avg_runs_conceded,
                     win_pct_batting_first=excluded.win_pct_batting_first,
                     win_pct_batting_second=excluded.win_pct_batting_second,
                     toss_win_pct=excluded.toss_win_pct,
                     elo_rating=excluded.elo_rating,
                     last_updated=excluded.last_updated""",
                (season, lid, format_str, team, t_type, gp, s["wins"], s["losses"],
                 round(avg_bat1, 1), round(avg_bat2, 1), round(avg_conc, 1),
                 round(wp_bat1, 3), round(wp_bat2, 3), round(toss_pct, 3),
                 round(team_elo, 1), now)
            )
            upserted += 1
        conn.commit()

    logger.info(f"[CRICKET] Team stats: {upserted} team-season rows written.")
    return upserted


# ── Main orchestrator ──────────────────────────────────────────────────────────
def run_fetch(
    format_str: str = "T20",
    sources: list = None,
    seasons: list = None,
    elo_only: bool = False,
) -> dict:
    """
    Main entry: fetch all historical cricket data.
    Returns summary dict.
    """
    ensure_tables()
    sources  = sources or ["cricsheet", "apisports"]
    seasons  = seasons or DEFAULT_SEASONS

    summary = {
        "format":           format_str,
        "total_stored":     0,
        "sources":          [],
        "team_stats_rows":  0,
        "venue_stats_rows": 0,
        "elo_teams":        0,
        "errors":           [],
    }

    if not elo_only:
        # ── Source 1: Cricsheet (free, no key needed) ─────────────────────────
        if "cricsheet" in sources:
            logger.info(f"[CRICKET] Fetching Cricsheet {format_str} data (free)...")
            # Download full format archive (includes all competitions)
            n1 = download_cricsheet(format_str, ipl_only=False)
            # Also download IPL-specific archive for richer data
            n2 = download_cricsheet(format_str, ipl_only=True)
            total_cs = n1 + n2
            summary["total_stored"] += total_cs
            summary["sources"].append(f"Cricsheet: {total_cs} new matches stored")

        # ── Source 2: API Sports ──────────────────────────────────────────────
        if "apisports" in sources and APISPORTS_KEY:
            logger.info("[CRICKET] Fetching API Sports fixtures...")
            total_api = 0
            for lid in [1, 9, 2, 167]:   # IPL, T20 WC, Hundred, BBL
                for season in seasons:
                    n = fetch_apisports_cricket(lid, season, format_str)
                    total_api += n
            summary["total_stored"] += total_api
            summary["sources"].append(f"API Sports: {total_api} new matches stored")

    # ── Compute stats from all stored data ────────────────────────────────────
    logger.info(f"[CRICKET/{format_str}] Computing ELO + team/venue stats...")
    t_rows = compute_team_stats(format_str)
    v_rows = compute_venue_stats(format_str)
    elo_map = compute_elo_from_matches(format_str)

    summary["team_stats_rows"]  = t_rows
    summary["venue_stats_rows"] = v_rows
    summary["elo_teams"]        = len(elo_map)

    # Final count
    try:
        with get_conn() as conn:
            n = conn.execute(
                "SELECT COUNT(*) FROM cricket_matches WHERE format=?", (format_str,)
            ).fetchone()[0]
    except Exception:
        n = 0

    summary["total_in_db"] = n
    min_req = 150 if format_str == "T20" else 80
    summary["data_phase_cleared"] = n >= min_req

    logger.info(
        f"\n{'='*60}\n"
        f"  CRICKET [{format_str}] DATA FETCH COMPLETE\n"
        f"  Total matches in DB     : {n}\n"
        f"  Data phase cleared      : {'✓ YES' if n >= min_req else f'✗ NO ({n}/{min_req})'}\n"
        f"  Team stat rows          : {t_rows}\n"
        f"  Venue stat rows         : {v_rows}\n"
        f"  ELO teams computed      : {len(elo_map)}\n"
        f"{'='*60}"
    )

    if elo_map:
        top10 = sorted(elo_map.items(), key=lambda x: x[1], reverse=True)[:10]
        logger.info("  TOP 10 ELO RATINGS (merged):")
        for team, elo_val in top10:
            t_type = get_team_type(team)
            logger.info(f"    [{t_type:9s}] {team:35s} {elo_val:.0f}")

    # Log separated top ELOs for visibility
    elo_pools = compute_separated_elos(format_str)
    top5_nat = sorted(elo_pools["national"].items(),  key=lambda x: x[1], reverse=True)[:5]
    top5_fra = sorted(elo_pools["franchise"].items(), key=lambda x: x[1], reverse=True)[:5]
    if top5_nat:
        logger.info("  TOP 5 NATIONAL ELOs:")
        for team, val in top5_nat:
            logger.info(f"    {team:35s} {val:.0f}")
    if top5_fra:
        logger.info("  TOP 5 FRANCHISE (IPL) ELOs:")
        for team, val in top5_fra:
            logger.info(f"    {team:35s} {val:.0f}")

    return summary


# ── Walk-forward backtest (franchise vs national) ─────────────────────────────
def run_backtest_separated(format_str: str = "T20") -> dict:
    """
    Walk-forward Brier score backtest using SEPARATED ELO pools.
    Runs separately for:
      - ICC T20 WC / International matches  → national ELO
      - IPL matches                          → franchise ELO

    Walk-forward protocol:
      For each match (ordered by date), predict using ELO built from ALL PRIOR
      matches (no lookahead). Then update ELO after prediction.

    Returns dict with Brier scores and calibration bins for both pools.
    """
    HFA = 35

    try:
        with get_conn() as conn:
            rows = conn.execute(
                """SELECT date, league_name, home_team, away_team, winner
                   FROM cricket_matches
                   WHERE format = ? AND status IN ('FT','FINISHED','COMPLETE')
                     AND home_team IS NOT NULL AND away_team IS NOT NULL
                     AND winner IS NOT NULL AND winner != ''
                   ORDER BY date ASC""",
                (format_str,)
            ).fetchall()
    except sqlite3.OperationalError:
        return {"error": "cricket_matches table not found"}

    # Separate match rows by type
    ipl_rows   = []
    intl_rows  = []
    for row in rows:
        ht = row["home_team"]
        at = row["away_team"]
        if (ht in FRANCHISE_TEAMS) and (at in FRANCHISE_TEAMS):
            ipl_rows.append(row)
        elif (ht not in FRANCHISE_TEAMS) and (at not in FRANCHISE_TEAMS):
            intl_rows.append(row)
        # mixed: skip

    def _walk_forward_brier(match_rows: list, label: str) -> dict:
        """Walk-forward ELO + Brier score over a list of match rows."""
        elo       = {}
        gc        = {}
        brier_sum = 0.0
        n_bets    = 0

        # Calibration bins: [0-10%, 10-20%, ... 90-100%]
        bins_pred = [[] for _ in range(10)]
        bins_act  = [[] for _ in range(10)]

        for row in match_rows:
            ht     = row["home_team"]
            at     = row["away_team"]
            winner = row["winner"]

            elo.setdefault(ht, ELO_DEFAULT)
            elo.setdefault(at, ELO_DEFAULT)
            gc.setdefault(ht, 0)
            gc.setdefault(at, 0)

            # Predict BEFORE updating ELO (walk-forward — no lookahead)
            e_h = 1 / (1 + 10 ** (-((elo[ht] + HFA) - elo[at]) / 400))
            actual_h = 1.0 if winner == ht else 0.0

            # Brier score: (p - outcome)^2
            brier_sum += (e_h - actual_h) ** 2
            n_bets    += 1

            # Calibration bin assignment
            bin_idx = min(int(e_h * 10), 9)
            bins_pred[bin_idx].append(e_h)
            bins_act[bin_idx].append(actual_h)

            # Update ELO AFTER prediction
            k_h = ELO_K_EARLY if gc[ht] < 20 else ELO_K
            k_a = ELO_K_EARLY if gc[at] < 20 else ELO_K
            e_a = 1 - e_h
            s_h = actual_h
            s_a = 1 - actual_h
            elo[ht] += k_h * (s_h - e_h)
            elo[at] += k_a * (s_a - e_a)
            gc[ht]  += 1
            gc[at]  += 1

        brier = brier_sum / n_bets if n_bets > 0 else None

        # Build calibration table
        cal_table = []
        for i in range(10):
            if bins_pred[i]:
                avg_pred   = sum(bins_pred[i]) / len(bins_pred[i])
                avg_actual = sum(bins_act[i])  / len(bins_act[i])
                cal_table.append({
                    "bin":        f"{i*10}-{(i+1)*10}%",
                    "n":          len(bins_pred[i]),
                    "avg_pred":   round(avg_pred * 100, 1),
                    "avg_actual": round(avg_actual * 100, 1),
                    "error_pp":   round((avg_pred - avg_actual) * 100, 1),
                })

        return {
            "label":       label,
            "n_matches":   n_bets,
            "brier_score": round(brier, 5) if brier is not None else None,
            "calibration": cal_table,
        }

    ipl_result  = _walk_forward_brier(ipl_rows,  "IPL_FRANCHISE")
    intl_result = _walk_forward_brier(intl_rows, "INTERNATIONAL")

    logger.info(
        f"[BACKTEST/CRICKET/{format_str}] "
        f"IPL Brier={ipl_result['brier_score']} (n={ipl_result['n_matches']}) | "
        f"INTL Brier={intl_result['brier_score']} (n={intl_result['n_matches']})"
    )
    return {
        "format":        format_str,
        "ipl_franchise": ipl_result,
        "international": intl_result,
    }


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EyeBlackIQ cricket historical data fetcher")
    parser.add_argument("--format",   default="T20", choices=["T20","ODI","TEST"])
    parser.add_argument("--source",   default=None, nargs="+",
                        choices=["cricsheet","apisports","kaggle"],
                        help="Data sources (default: cricsheet + apisports)")
    parser.add_argument("--seasons",  type=int, nargs="+", default=DEFAULT_SEASONS)
    parser.add_argument("--elo-only",  action="store_true",
                        help="Only recompute ELO/team stats from existing DB data")
    parser.add_argument("--status",    action="store_true",
                        help="Print DB status and exit")
    parser.add_argument("--backtest",  action="store_true",
                        help="Run walk-forward Brier score backtest (franchise vs national)")
    args = parser.parse_args()

    if args.status:
        ensure_tables()
        with get_conn() as conn:
            for fmt in ["T20","ODI"]:
                n = conn.execute(
                    "SELECT COUNT(*) FROM cricket_matches WHERE format=?", (fmt,)
                ).fetchone()[0]
                print(f"  Cricket {fmt}: {n} matches in DB")
            n_v = conn.execute("SELECT COUNT(*) FROM cricket_venue_stats").fetchone()[0]
            n_t = conn.execute("SELECT COUNT(*) FROM cricket_team_stats").fetchone()[0]
        print(f"  Venue stats  : {n_v} venues")
        print(f"  Team stats   : {n_t} team-seasons")
        print(f"  APISPORTS_KEY: {'SET' if APISPORTS_KEY else 'MISSING'}")
    elif args.backtest:
        result = run_backtest_separated(args.format)
        print(f"\n{'='*65}")
        print(f"  CRICKET ELO BACKTEST — {result['format']} — Walk-Forward")
        print(f"{'='*65}")
        for pool_key in ["ipl_franchise", "international"]:
            p = result[pool_key]
            print(f"\n  [{p['label']}] n={p['n_matches']}  Brier={p['brier_score']}")
            print(f"  {'Bin':12s} {'N':>6} {'Pred%':>8} {'Actual%':>8} {'Error':>7}")
            print(f"  {'-'*48}")
            for row in p["calibration"]:
                flag = " *** OVERCONFIDENT" if row["error_pp"] > 3 else (
                       " *   underconfident" if row["error_pp"] < -3 else "")
                print(f"  {row['bin']:12s} {row['n']:>6} {row['avg_pred']:>7.1f}% "
                      f"{row['avg_actual']:>7.1f}%  {row['error_pp']:>+6.1f}pp{flag}")
        print(f"{'='*65}\n")
    else:
        result = run_fetch(
            format_str = args.format,
            sources    = args.source,
            seasons    = args.seasons,
            elo_only   = args.elo_only,
        )
        print(json.dumps({k: v for k, v in result.items() if k != "sources"}, indent=2))
        print("\nSource breakdown:")
        for line in result.get("sources", []):
            print(f"  {line}")
