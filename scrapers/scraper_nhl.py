"""
EyeBlackIQ — scraper_nhl.py
NHL schedule, results, and player SOG stats via NHL Official API + ESPN.

Usage:
  python scrapers/scraper_nhl.py --date 2026-03-21 --mode schedule
  python scrapers/scraper_nhl.py --date 2026-03-21 --mode results
  python scrapers/scraper_nhl.py --date 2026-03-21 --mode props

Output: JSON to stdout
Errors: /logs/scraper_errors.log
"""
import sys
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
logger = logging.getLogger("scraper_nhl")

NHL_API  = "https://api-web.nhle.com/v1"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl"
HEADERS  = {"User-Agent": "EyeBlackIQ/2.1"}


def _get(url: str, params: dict = None) -> dict:
    for attempt in range(3):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=12)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            logger.warning(f"GET {url} attempt {attempt+1} failed: {e}")
            time.sleep(0.5 * (attempt + 1))
    logger.error(f"GET {url} failed after 3 attempts")
    return {}


def schedule(date_str: str) -> list:
    """Return NHL schedule for date from official NHL API."""
    data = _get(f"{NHL_API}/schedule/{date_str}")
    games = []
    for week in data.get("gameWeek", []):
        for g in week.get("games", []):
            home = g.get("homeTeam", {})
            away = g.get("awayTeam", {})
            games.append({
                "game_id":    g.get("id"),
                "home":       home.get("placeName", {}).get("default", "") + " " + home.get("commonName", {}).get("default", ""),
                "away":       away.get("placeName", {}).get("default", "") + " " + away.get("commonName", {}).get("default", ""),
                "home_abbr":  home.get("abbrev", ""),
                "away_abbr":  away.get("abbrev", ""),
                "home_id":    home.get("id"),
                "away_id":    away.get("id"),
                "start_time": g.get("startTimeUTC", ""),
                "status":     g.get("gameState", ""),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
                "game_type":  g.get("gameType"),
            })
        time.sleep(0.5)
    return games


def results(date_str: str) -> list:
    """Return final scores for a date (gameState=FINAL or OFF)."""
    all_games = schedule(date_str)
    return [g for g in all_games if g.get("status") in ("FINAL", "OFF")]


def get_player_game_log(player_id: int, season: str = "20252026") -> list:
    """
    Fetch player game log for current season.
    season format: e.g. "20252026" for 2025-26
    Returns list of game entries with SOG, goals, assists.
    """
    data = _get(f"{NHL_API}/player/{player_id}/game-log/{season}/2")  # 2 = regular season
    log = []
    for entry in data.get("gameLog", []):
        log.append({
            "game_id":       entry.get("gameId"),
            "date":          entry.get("gameDate"),
            "home_road":     entry.get("homeRoadFlag"),
            "opponent":      entry.get("opponentAbbrev"),
            "shots_on_goal": entry.get("shotsOnGoal"),
            "goals":         entry.get("goals"),
            "assists":       entry.get("assists"),
            "points":        entry.get("points"),
            "toi":           entry.get("toi"),
        })
        time.sleep(0.5)
    return log


def props(date_str: str) -> list:
    """
    NHL SOG props.
    # TODO: OddsAPI endpoint for NHL player_shots_on_goal market when credits restored
    Returns schedule with note — prop lines require OddsAPI.
    """
    return [{
        "note": "NHL SOG prop lines require OddsAPI (credits depleted). TODO: OddsAPI when credits restored.",
        "date": date_str,
        "games": schedule(date_str),
    }]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NHL scraper")
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
