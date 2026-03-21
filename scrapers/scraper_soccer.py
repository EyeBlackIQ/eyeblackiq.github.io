"""
EyeBlackIQ — scraper_soccer.py
Soccer schedule, results, and Elo ratings via ESPN API + Club Elo.

Usage:
  python scrapers/scraper_soccer.py --date 2026-03-21 --mode schedule
  python scrapers/scraper_soccer.py --date 2026-03-21 --mode results
  python scrapers/scraper_soccer.py --date 2026-03-21 --mode props

Output: JSON to stdout
Errors: /logs/scraper_errors.log
"""
import sys
import csv
import io
import json
import time
import argparse
import logging
from datetime import datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).parent.parent
LOG_FILE = BASE_DIR / "logs" / "scraper_errors.log"
LOG_FILE.parent.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler(sys.stderr)],
)
logger = logging.getLogger("scraper_soccer")

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer"
ELO_API   = "http://api.clubelo.com"
HEADERS   = {"User-Agent": "EyeBlackIQ/2.1"}

# ESPN league slugs
LEAGUES = {
    "EPL":       "eng.1",
    "LALIGA":    "esp.1",
    "BUNDESLIGA":"ger.1",
    "SERIE_A":   "ita.1",
    "LIGUE_1":   "fra.1",
    "UEFA_CL":   "uefa.champions",
    "UEFA_EL":   "uefa.europa",
}


def _get(url: str, params: dict = None, text_mode: bool = False):
    """GET with retry and 0.5s rate limit."""
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=12)
            r.raise_for_status()
            return r.text if text_mode else r.json()
        except Exception as e:
            logger.warning(f"GET {url} attempt {attempt+1} failed: {e}")
            time.sleep(0.5 * (attempt + 1))
    logger.error(f"GET {url} failed after 3 attempts")
    return "" if text_mode else {}


def _fmt_date(date_str: str) -> str:
    return date_str.replace("-", "")


def schedule(date_str: str, leagues: list = None) -> list:
    """Return schedule for all tracked leagues on a date."""
    if leagues is None:
        leagues = list(LEAGUES.keys())
    events = []
    for league_key in leagues:
        slug = LEAGUES.get(league_key)
        if not slug:
            continue
        data = _get(f"{ESPN_BASE}/{slug}/scoreboard", {"dates": _fmt_date(date_str)})
        for ev in data.get("events", []):
            comp  = ev.get("competitions", [{}])[0]
            teams = comp.get("competitors", [])
            home  = next((t for t in teams if t.get("homeAway") == "home"), {})
            away  = next((t for t in teams if t.get("homeAway") == "away"), {})
            status = ev.get("status", {}).get("type", {}).get("name", "")
            events.append({
                "event_id":   ev.get("id", ""),
                "league":     league_key,
                "home":       home.get("team", {}).get("displayName", ""),
                "away":       away.get("team", {}).get("displayName", ""),
                "home_abbr":  home.get("team", {}).get("abbreviation", ""),
                "away_abbr":  away.get("team", {}).get("abbreviation", ""),
                "start_time": ev.get("date", ""),
                "status":     status,
                "home_score": home.get("score"),
                "away_score": away.get("score"),
            })
        time.sleep(0.5)
    return events


def results(date_str: str) -> list:
    """Return final scores for all leagues on a date."""
    all_events = schedule(date_str)
    return [e for e in all_events if e.get("status") in ("STATUS_FINAL", "STATUS_FINAL_AET", "STATUS_FULL_TIME")]


def get_club_elo(club_name: str) -> dict:
    """
    Fetch Club Elo history for a team.
    Returns most recent Elo rating.
    """
    text = _get(f"{ELO_API}/{club_name}", text_mode=True)
    if not text or "Rank" not in text:
        return {"club": club_name, "elo": None, "error": "Not found"}
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return {"club": club_name, "elo": None}
    latest = rows[-1]
    return {
        "club":    latest.get("Club", club_name),
        "country": latest.get("Country", ""),
        "level":   latest.get("Level", ""),
        "elo":     float(latest.get("Elo", 0) or 0),
        "as_of":   latest.get("To", ""),
    }


def props(date_str: str) -> list:
    """
    Soccer SOT / goals props.
    # TODO: OddsAPI endpoint for soccer player_shots_on_target market when credits restored
    """
    return [{
        "note": "Soccer prop lines require OddsAPI (credits depleted). TODO: OddsAPI when credits restored.",
        "date": date_str,
        "games": schedule(date_str, leagues=["EPL", "LALIGA", "BUNDESLIGA"]),
    }]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Soccer scraper")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--mode",  default="schedule", choices=["schedule", "results", "props"])
    args = parser.parse_args()

    if args.mode == "schedule":
        out = schedule(args.date)
    elif args.mode == "results":
        out = results(args.date)
    else:
        out = props(args.date)

    print(json.dumps(out, indent=2, default=str))
