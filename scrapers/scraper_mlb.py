"""
EyeBlackIQ — scraper_mlb.py
MLB schedule, results, and pitcher stats via MLB Stats API + ESPN.

Usage:
  python scrapers/scraper_mlb.py --date 2026-03-21 --mode schedule
  python scrapers/scraper_mlb.py --date 2026-03-21 --mode results
  python scrapers/scraper_mlb.py --date 2026-03-21 --mode props

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
logger = logging.getLogger("scraper_mlb")

MLB_API  = "https://statsapi.mlb.com/api/v1"
ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb"
HEADERS  = {"User-Agent": "EyeBlackIQ/2.1"}


def _get(url: str, params: dict = None) -> dict:
    """GET with retry and 0.5s rate limit."""
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
    """Return MLB schedule for date from MLB Stats API."""
    data = _get(f"{MLB_API}/schedule", {
        "sportId": 1, "date": date_str,
        "hydrate": "linescore,team,probablePitcher(stats)"
    })
    games = []
    for date_block in data.get("dates", []):
        for g in date_block.get("games", []):
            home = g.get("teams", {}).get("home", {})
            away = g.get("teams", {}).get("away", {})
            home_sp = home.get("probablePitcher", {})
            away_sp = away.get("probablePitcher", {})
            games.append({
                "game_pk":    g.get("gamePk"),
                "home":       home.get("team", {}).get("name", ""),
                "away":       away.get("team", {}).get("name", ""),
                "home_abbr":  home.get("team", {}).get("abbreviation", ""),
                "away_abbr":  away.get("team", {}).get("abbreviation", ""),
                "venue":      g.get("venue", {}).get("name", ""),
                "start_time": g.get("gameDate", ""),
                "status":     g.get("status", {}).get("detailedState", ""),
                "home_sp":    home_sp.get("fullName", "TBD"),
                "home_sp_id": home_sp.get("id"),
                "away_sp":    away_sp.get("fullName", "TBD"),
                "away_sp_id": away_sp.get("id"),
                "home_score": home.get("score"),
                "away_score": away.get("score"),
            })
        time.sleep(0.5)
    return games


def results(date_str: str) -> list:
    """Return final scores for a date."""
    all_games = schedule(date_str)
    return [g for g in all_games if "Final" in (g.get("status") or "")]


def get_pitcher_stats(player_id: int, season: int = 2026) -> dict:
    """
    Fetch season pitcher stats for a player.
    Returns dict with ERA, strikeouts, innings, K/9.
    """
    data = _get(f"{MLB_API}/people/{player_id}/stats", {
        "stats": "season", "group": "pitching", "season": season
    })
    splits = []
    for stat_block in data.get("stats", []):
        splits.extend(stat_block.get("splits", []))
    if not splits:
        return {}
    s = splits[0].get("stat", {})
    return {
        "player_id":    player_id,
        "season":       season,
        "era":          s.get("era"),
        "strikeouts":   s.get("strikeOuts"),
        "innings":      s.get("inningsPitched"),
        "k_per_9":      s.get("strikeoutsPer9Inn"),
        "whip":         s.get("whip"),
        "games_started": s.get("gamesStarted"),
    }


def props(date_str: str) -> list:
    """
    MLB pitcher strikeout props.
    # TODO: OddsAPI endpoint for MLB pitcher_strikeouts market when credits restored
    Returns starter list with historical K stats for manual line comparison.
    """
    games = schedule(date_str)
    prop_candidates = []
    for g in games:
        for role, pid, name in [
            ("home", g.get("home_sp_id"), g.get("home_sp")),
            ("away", g.get("away_sp_id"), g.get("away_sp")),
        ]:
            if pid and name and name != "TBD":
                stats = get_pitcher_stats(pid)
                prop_candidates.append({
                    "game":   f"{g['away']} @ {g['home']}",
                    "role":   role,
                    "pitcher": name,
                    "player_id": pid,
                    "era":    stats.get("era"),
                    "k_per_9": stats.get("k_per_9"),
                    "starts": stats.get("games_started"),
                    "strikeouts_season": stats.get("strikeouts"),
                    "note":   "TODO: OddsAPI strikeout line when credits restored",
                })
                time.sleep(0.5)
    return prop_candidates


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="MLB scraper")
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
