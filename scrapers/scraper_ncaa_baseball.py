"""
EyeBlackIQ — scraper_ncaa_baseball.py
NCAA Baseball schedule, results, and team stats via ESPN API.

Usage:
  python scrapers/scraper_ncaa_baseball.py --date 2026-03-21 --mode schedule
  python scrapers/scraper_ncaa_baseball.py --date 2026-03-21 --mode results
  python scrapers/scraper_ncaa_baseball.py --date 2026-03-21 --mode props

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
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stderr),
    ]
)
logger = logging.getLogger("scraper_ncaa_baseball")

ESPN_URL = "https://site.api.espn.com/apis/site/v2/sports/baseball/college-baseball"
HEADERS  = {"User-Agent": "EyeBlackIQ/2.1"}


def _get(url: str, params: dict = None) -> dict:
    """GET with retry and 0.5s rate limit courtesy."""
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


def _fmt_date(date_str: str) -> str:
    """Convert YYYY-MM-DD to YYYYMMDD for ESPN."""
    return date_str.replace("-", "")


def schedule(date_str: str) -> list:
    """
    Return schedule events for a date.
    Returns list of {event_id, home, away, start_time, status, home_score, away_score}.
    """
    data = _get(f"{ESPN_URL}/scoreboard", {"dates": _fmt_date(date_str)})
    events = data.get("events", [])
    results = []
    for ev in events:
        comp = ev.get("competitions", [{}])[0]
        teams = comp.get("competitors", [])
        home = next((t for t in teams if t.get("homeAway") == "home"), {})
        away = next((t for t in teams if t.get("homeAway") == "away"), {})
        status = ev.get("status", {}).get("type", {}).get("name", "")
        results.append({
            "event_id":   ev.get("id", ""),
            "home":       home.get("team", {}).get("displayName", ""),
            "away":       away.get("team", {}).get("displayName", ""),
            "home_abbr":  home.get("team", {}).get("abbreviation", ""),
            "away_abbr":  away.get("team", {}).get("abbreviation", ""),
            "start_time": ev.get("date", ""),
            "status":     status,
            "home_score": home.get("score"),
            "away_score": away.get("score"),
            "venue":      comp.get("venue", {}).get("fullName", ""),
            "neutral":    comp.get("neutralSite", False),
        })
        time.sleep(0.5)
    return results


def results(date_str: str) -> list:
    """Return final scores for a date (status=STATUS_FINAL only)."""
    all_events = schedule(date_str)
    return [e for e in all_events if e.get("status") in ("STATUS_FINAL", "STATUS_FINAL_AET")]


def props(date_str: str) -> list:
    """
    NCAA Baseball props — not available via ESPN API.
    # TODO: OddsAPI endpoint for NCAA baseball pitcher strikeout props
    Returns empty list with note.
    """
    return [{"note": "NCAA Baseball props not available from free endpoints. TODO: OddsAPI when credits restored."}]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NCAA Baseball scraper")
    parser.add_argument("--date", default=datetime.now().strftime("%Y-%m-%d"), help="YYYY-MM-DD")
    parser.add_argument("--mode", default="schedule", choices=["schedule", "results", "props"])
    args = parser.parse_args()

    if args.mode == "schedule":
        output = schedule(args.date)
    elif args.mode == "results":
        output = results(args.date)
    else:
        output = props(args.date)

    print(json.dumps(output, indent=2, default=str))
