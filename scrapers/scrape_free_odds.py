"""
EyeBlackIQ — scrapers/scrape_free_odds.py
Free odds scraper using ESPN Core API (no key required).

Workflow:
  1. Pull scheduled games from ESPN scoreboard endpoints (to get event IDs)
  2. Hit ESPN Core odds endpoint per event to get ML, spread, total
  3. Cache raw JSON to scrapers/cache/espn_odds_{sport}_{date}.json
  4. Populate module-level lines_cache dict (importable by model files)
  5. Return unified format: {home, away, ml_home, ml_away, total, spread, start_utc, source}

Supported sports:
  NHL, MLB, Soccer (EPL, LaLiga, UCL, Bundesliga, SerieA, Ligue1), NCAA Baseball

Usage:
  python scrapers/scrape_free_odds.py --date 2026-03-21
  python scrapers/scrape_free_odds.py --date 2026-03-21 --sport nhl
  python scrapers/scrape_free_odds.py --date 2026-03-21 --dry-run
"""
import os
import sys
import json
import time
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ── Env / logging ──────────────────────────────────────────────────────────────
_ENV = Path(__file__).parent.parent.parent / "quant-betting" / "soccer" / ".claude" / "worktrees" / "admiring-allen" / ".env"
if _ENV.exists():
    load_dotenv(_ENV)
else:
    load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

BASE_DIR  = Path(__file__).parent.parent
CACHE_DIR = BASE_DIR / "scrapers" / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

# ── Importable lines cache — populated by run_scrape() ────────────────────────
# Key: "{sport}_{date}"  e.g. "nhl_2026-03-21"
# Value: list of unified game dicts
lines_cache: dict = {}

# ── ESPN endpoint config ───────────────────────────────────────────────────────
ESPN_SITE  = "https://site.api.espn.com/apis/site/v2/sports"
ESPN_CORE  = "https://sports.core.api.espn.com/v2/sports"

SCOREBOARD_URLS = {
    "nhl":        f"{ESPN_SITE}/hockey/nhl/scoreboard",
    "mlb":        f"{ESPN_SITE}/baseball/mlb/scoreboard",
    "ncaa_bb":    f"{ESPN_SITE}/baseball/college-baseball/scoreboard",
    "soccer_epl": f"{ESPN_SITE}/soccer/eng.1/scoreboard",
    "soccer_esp": f"{ESPN_SITE}/soccer/esp.1/scoreboard",
    "soccer_ucl": f"{ESPN_SITE}/soccer/uefa.champions/scoreboard",
    "soccer_ger": f"{ESPN_SITE}/soccer/ger.1/scoreboard",
    "soccer_ita": f"{ESPN_SITE}/soccer/ita.1/scoreboard",
    "soccer_fra": f"{ESPN_SITE}/soccer/fra.1/scoreboard",
}

CORE_ODDS_PATTERNS = {
    "nhl":        f"{ESPN_CORE}/hockey/leagues/nhl/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "mlb":        f"{ESPN_CORE}/baseball/leagues/mlb/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "ncaa_bb":    f"{ESPN_CORE}/baseball/leagues/college-baseball/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_epl": f"{ESPN_CORE}/soccer/leagues/eng.1/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_esp": f"{ESPN_CORE}/soccer/leagues/esp.1/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_ucl": f"{ESPN_CORE}/soccer/leagues/uefa.champions/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_ger": f"{ESPN_CORE}/soccer/leagues/ger.1/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_ita": f"{ESPN_CORE}/soccer/leagues/ita.1/events/{{ev_id}}/competitions/{{comp_id}}/odds",
    "soccer_fra": f"{ESPN_CORE}/soccer/leagues/fra.1/events/{{ev_id}}/competitions/{{comp_id}}/odds",
}

# Human-friendly display names
SPORT_LABELS = {
    "nhl":        "NHL",
    "mlb":        "MLB",
    "ncaa_bb":    "NCAA Baseball",
    "soccer_epl": "EPL",
    "soccer_esp": "LaLiga",
    "soccer_ucl": "UCL",
    "soccer_ger": "Bundesliga",
    "soccer_ita": "Serie A",
    "soccer_fra": "Ligue 1",
}

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "EyeBlackIQ/1.0 (research)"})


# ── HTTP helpers ───────────────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def _get(url: str, params: dict = None, timeout: int = 15) -> Optional[dict]:
    """GET with retry. Returns parsed JSON or None on failure."""
    resp = SESSION.get(url, params=params or {}, timeout=timeout)
    if resp.status_code == 404:
        return None
    if resp.status_code == 429:
        logger.warning("ESPN rate-limited (429) — backing off")
        time.sleep(5)
        resp.raise_for_status()
    resp.raise_for_status()
    return resp.json()


# ── Scoreboard scraper — returns list of event metadata dicts ──────────────────
def fetch_scoreboard(sport_key: str, date_str: str) -> list:
    """
    Pull ESPN scoreboard for sport_key on date_str.
    Returns list of event metadata dicts with keys:
      ev_id, comp_id, home, away, start_utc, has_odds_in_competitions
    """
    url    = SCOREBOARD_URLS.get(sport_key)
    if not url:
        logger.warning(f"No scoreboard URL for sport_key={sport_key}")
        return []

    date_compact = date_str.replace("-", "")
    params = {"dates": date_compact, "limit": 200}
    if sport_key == "ncaa_bb":
        params["groups"] = "50"   # Division I

    data = _get(url, params=params)
    if not data:
        logger.warning(f"[{sport_key}] No scoreboard data for {date_str}")
        return []

    events_raw = data.get("events", [])
    logger.info(f"[{sport_key}] Scoreboard: {len(events_raw)} events on {date_str}")

    events = []
    for ev in events_raw:
        ev_id = ev.get("id", "")
        comps = ev.get("competitions", [])
        if not comps:
            continue
        comp  = comps[0]
        comp_id = comp.get("id", ev_id)

        competitors = comp.get("competitors", [])
        home_name, away_name = "?", "?"
        for c in competitors:
            team_name = c.get("team", {}).get("displayName", c.get("team", {}).get("name", "?"))
            if c.get("homeAway") == "home":
                home_name = team_name
            else:
                away_name = team_name

        # Check if competition already has embedded odds (NCAA sometimes does)
        embedded_odds = comp.get("odds", [])

        events.append({
            "ev_id":       ev_id,
            "comp_id":     comp_id,
            "home":        home_name,
            "away":        away_name,
            "start_utc":   ev.get("date", ""),
            "embedded_odds": embedded_odds,
        })

    return events


# ── Core odds parser ───────────────────────────────────────────────────────────
def parse_core_odds(odds_data: dict, home: str, away: str, start_utc: str, source: str) -> Optional[dict]:
    """
    Parse ESPN Core odds response into unified game dict.
    Returns None if no usable ML lines found.

    Unified format:
      home, away, ml_home, ml_away, total, total_over_odds, total_under_odds,
      spread_home, spread_home_odds, spread_away_odds, start_utc, source
    """
    if not odds_data:
        return None

    # The Core odds endpoint returns {"items": [...]} where each item is a provider
    items = odds_data.get("items", [])
    if not items:
        # Sometimes the payload is the provider object itself (no "items" wrapper)
        items = [odds_data]

    ml_home = ml_away = None
    total = total_over = total_under = None
    spread_home = spread_home_odds = spread_away_odds = None

    for provider in items:
        # ML lines
        hl = provider.get("homeTeamOdds", {})
        al = provider.get("awayTeamOdds", {})
        if hl.get("moneyLine") and ml_home is None:
            ml_home = hl["moneyLine"]
        if al.get("moneyLine") and ml_away is None:
            ml_away = al["moneyLine"]

        # Spread
        if hl.get("spreadOdds") and spread_home is None:
            spread_home       = provider.get("spread")
            spread_home_odds  = hl.get("spreadOdds")
            spread_away_odds  = al.get("spreadOdds")

        # Totals
        if provider.get("overUnder") and total is None:
            total       = provider["overUnder"]
            total_over  = provider.get("overOdds")
            total_under = provider.get("underOdds")

        # Stop if we have the essentials
        if ml_home and ml_away:
            break

    if ml_home is None and ml_away is None:
        return None

    return {
        "home":              home,
        "away":              away,
        "ml_home":           ml_home,
        "ml_away":           ml_away,
        "total":             total,
        "total_over_odds":   total_over,
        "total_under_odds":  total_under,
        "spread_home":       spread_home,
        "spread_home_odds":  spread_home_odds,
        "spread_away_odds":  spread_away_odds,
        "start_utc":         start_utc,
        "source":            source,
    }


def fetch_core_odds(sport_key: str, ev_id: str, comp_id: str) -> Optional[dict]:
    """
    Hit ESPN Core odds endpoint for one event.
    Returns raw JSON or None.
    """
    pattern = CORE_ODDS_PATTERNS.get(sport_key)
    if not pattern:
        return None
    url  = pattern.format(ev_id=ev_id, comp_id=comp_id)
    data = _get(url)
    return data


# ── Per-sport scraper ──────────────────────────────────────────────────────────
def scrape_sport(sport_key: str, date_str: str) -> list:
    """
    Scrape all available odds for sport_key on date_str.
    Returns list of unified game dicts.
    Also saves raw data to cache.

    NCAA Baseball: uses embedded odds if available (Core odds endpoint
    often returns 404 for college events), falls back to schedule-only.
    """
    label   = SPORT_LABELS.get(sport_key, sport_key)
    events  = fetch_scoreboard(sport_key, date_str)
    if not events:
        return []

    results     = []
    raw_by_ev   = {}

    for ev in events:
        ev_id   = ev["ev_id"]
        comp_id = ev["comp_id"]
        home    = ev["home"]
        away    = ev["away"]
        start   = ev["start_utc"]

        # NCAA: check embedded odds first (often more reliable)
        embedded = ev.get("embedded_odds", [])
        if embedded:
            game = _parse_embedded_odds(embedded, home, away, start, f"espn_embedded/{label}")
            if game:
                results.append(game)
                raw_by_ev[ev_id] = {"embedded": embedded, "home": home, "away": away}
                logger.debug(f"  [{label}] {away} @ {home}  ML: {game.get('ml_home')}/{game.get('ml_away')}  "
                             f"Total: {game.get('total')}  [embedded]")
                continue

        # Try Core odds endpoint
        raw = fetch_core_odds(sport_key, ev_id, comp_id)
        raw_by_ev[ev_id] = raw or {}

        if raw:
            game = parse_core_odds(raw, home, away, start, f"espn_core/{label}")
            if game:
                results.append(game)
                logger.debug(f"  [{label}] {away} @ {home}  ML: {game.get('ml_home')}/{game.get('ml_away')}  "
                             f"Total: {game.get('total')}")
            else:
                # No ML lines but we have schedule info
                results.append(_schedule_only(home, away, start, label))
        else:
            # No odds available — return schedule entry
            results.append(_schedule_only(home, away, start, label))

        time.sleep(0.15)   # gentle rate limiting

    # Cache raw data
    cache_file = CACHE_DIR / f"espn_odds_{sport_key}_{date_str}.json"
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump({"sport": sport_key, "date": date_str, "events": raw_by_ev,
                   "results": results, "scraped_at": datetime.now(timezone.utc).isoformat()},
                  f, indent=2)
    logger.info(f"[{label}] {len(results)} games — {sum(1 for g in results if g.get('ml_home'))} with ML odds "
                f"→ {cache_file.name}")

    return results


def _parse_embedded_odds(odds_list: list, home: str, away: str,
                         start_utc: str, source: str) -> Optional[dict]:
    """
    Parse the competitions[0].odds list that ESPN sometimes embeds
    directly in the scoreboard response.
    """
    ml_home = ml_away = None
    total = total_over = total_under = None
    spread_home = spread_home_odds = spread_away_odds = None

    for provider in odds_list:
        if provider is None:
            continue
        hl = provider.get("homeTeamOdds", {})
        al = provider.get("awayTeamOdds", {})
        if hl.get("moneyLine") and ml_home is None:
            ml_home = hl["moneyLine"]
        if al.get("moneyLine") and ml_away is None:
            ml_away = al["moneyLine"]
        if provider.get("overUnder") and total is None:
            total       = provider["overUnder"]
            total_over  = provider.get("overOdds")
            total_under = provider.get("underOdds")
        if hl.get("spreadOdds") and spread_home is None:
            spread_home       = provider.get("spread")
            spread_home_odds  = hl.get("spreadOdds")
            spread_away_odds  = al.get("spreadOdds")

    if ml_home is None and ml_away is None and total is None:
        return None

    return {
        "home":              home,
        "away":              away,
        "ml_home":           ml_home,
        "ml_away":           ml_away,
        "total":             total,
        "total_over_odds":   total_over,
        "total_under_odds":  total_under,
        "spread_home":       spread_home,
        "spread_home_odds":  spread_home_odds,
        "spread_away_odds":  spread_away_odds,
        "start_utc":         start_utc,
        "source":            source,
    }


def _schedule_only(home: str, away: str, start_utc: str, label: str) -> dict:
    """Return a schedule-only entry (no odds)."""
    return {
        "home": home, "away": away,
        "ml_home": None, "ml_away": None,
        "total": None, "total_over_odds": None, "total_under_odds": None,
        "spread_home": None, "spread_home_odds": None, "spread_away_odds": None,
        "start_utc": start_utc,
        "source": f"espn_schedule/{label}",
    }


# ── NCAA Baseball specific helper ─────────────────────────────────────────────
def get_ncaa_totals_from_espn(date_str: str) -> dict:
    """
    Try to extract O/U totals from ESPN for NCAA Baseball games.
    Returns dict keyed by "{away} @ {home}" with total line.

    Checks cached file first, then re-fetches if needed.
    Intended to be called from pods/ncaa_baseball/model.py.

    Returns:
      {"Auburn @ Florida": 9.5, ...}  — only games where total is available
    """
    cache_file = CACHE_DIR / f"espn_odds_ncaa_bb_{date_str}.json"

    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            cached = json.load(f)
        games = cached.get("results", [])
    else:
        games = scrape_sport("ncaa_bb", date_str)

    totals = {}
    for g in games:
        if g.get("total") is not None:
            key = f"{g['away']} @ {g['home']}"
            totals[key] = {
                "total":       g["total"],
                "over_odds":   g.get("total_over_odds"),
                "under_odds":  g.get("total_under_odds"),
            }
    logger.info(f"NCAA Baseball totals from ESPN [{date_str}]: {len(totals)} games with lines "
                f"(of {len(games)} scheduled)")
    return totals


# ── Main scraper entry point ───────────────────────────────────────────────────
def run_scrape(date_str: str, sports: list = None, dry_run: bool = False) -> dict:
    """
    Scrape ESPN odds for all requested sports on date_str.
    Populates lines_cache with results.

    Args:
      date_str: "YYYY-MM-DD"
      sports:   list of sport_keys (default: all in SCOREBOARD_URLS)
      dry_run:  if True, skip cache writes (still returns data)

    Returns:
      dict keyed by sport_key → list of unified game dicts
    """
    global lines_cache

    if sports is None:
        sports = list(SCOREBOARD_URLS.keys())

    all_results = {}
    for sport_key in sports:
        label = SPORT_LABELS.get(sport_key, sport_key)
        try:
            games = scrape_sport(sport_key, date_str)
            all_results[sport_key] = games
            lines_cache[f"{sport_key}_{date_str}"] = games
        except Exception as e:
            logger.error(f"[{label}] scrape failed: {e}", exc_info=True)
            all_results[sport_key] = []

    return all_results


def get_lines(sport_key: str, date_str: str) -> list:
    """
    Return cached lines for a sport/date.
    If not in memory cache, tries to load from disk.
    Returns empty list if not available.

    Intended import pattern in model files:
      from scrapers.scrape_free_odds import get_lines
      games = get_lines("nhl", "2026-03-21")
    """
    cache_key = f"{sport_key}_{date_str}"
    if cache_key in lines_cache:
        return lines_cache[cache_key]

    cache_file = CACHE_DIR / f"espn_odds_{sport_key}_{date_str}.json"
    if cache_file.exists():
        with open(cache_file, encoding="utf-8") as f:
            data = json.load(f)
        games = data.get("results", [])
        lines_cache[cache_key] = games
        return games

    return []


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ESPN free odds scraper (no API key required)")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date to scrape (YYYY-MM-DD)")
    parser.add_argument("--sport",   default="all",
                        help=f"Sport key or 'all'. Options: {', '.join(SCOREBOARD_URLS.keys())}")
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch and display but do not write cache files")
    args = parser.parse_args()

    if args.sport == "all":
        sports_to_run = list(SCOREBOARD_URLS.keys())
    else:
        if args.sport not in SCOREBOARD_URLS:
            print(f"Unknown sport '{args.sport}'. Options: {', '.join(SCOREBOARD_URLS.keys())}")
            sys.exit(1)
        sports_to_run = [args.sport]

    logger.info(f"ESPN free odds scraper — {args.date} — sports: {sports_to_run}")
    results = run_scrape(args.date, sports_to_run, dry_run=args.dry_run)

    print(f"\n{'='*60}")
    print(f"ESPN Odds Scrape — {args.date}")
    print(f"{'='*60}")
    total_games = total_with_odds = 0
    for sport_key, games in results.items():
        label     = SPORT_LABELS.get(sport_key, sport_key)
        with_odds = [g for g in games if g.get("ml_home") or g.get("total")]
        print(f"\n{label} ({len(games)} games, {len(with_odds)} with odds):")
        for g in games:
            ml_str = (f"ML {g['ml_home']:+d}/{g['ml_away']:+d}"
                      if g.get("ml_home") and g.get("ml_away") else "no ML")
            tot_str = f"  O/U {g['total']}" if g.get("total") else ""
            start = g.get("start_utc", "")[:16].replace("T", " ") if g.get("start_utc") else "TBD"
            print(f"  {g['away']:25s} @ {g['home']:25s}  {ml_str}{tot_str}  [{start}]")
        total_games     += len(games)
        total_with_odds += len(with_odds)

    print(f"\n{'='*60}")
    print(f"Total: {total_games} games across {len(results)} sports, {total_with_odds} with odds")
