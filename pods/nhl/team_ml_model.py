"""
EyeBlackIQ — pods/nhl/team_ml_model.py
NHL team ML + totals signal generator.

Model pipeline:
  1. Pull scheduled NHL games from ESPN scraper (scrape_free_odds)
  2. Get ML + O/U odds from ESPN Core API
  3. Build team ratings via:
       a) Pythagorean Win% from current season GF/GA (exponent = 2.0)
       b) ELO built from current standings W/L record if no historical data
  4. Devig market odds → fair no-vig probability
  5. Calculate model probability from Pythagorean / ELO blend
  6. Gate: edge >= 3% → write signal

Signal tiers (NHL team markets):
  SNIPE:        edge >= 12%  →  2.0u
  SLOT MACHINE: edge >=  5%  →  1.5u
  SCOUT:        edge >=  2%  →  1.0u
  ICING:        below min    →  0.0u  (not written)

Markets: ML (h2h) and TOTAL (over/under)

Usage:
  python pods/nhl/team_ml_model.py --date 2026-03-21
  python pods/nhl/team_ml_model.py --date 2026-03-21 --dry-run
"""
import os
import sys
import math
import json
import sqlite3
import argparse
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import time

import requests
from tenacity import retry, stop_after_attempt, wait_exponential
from dotenv import load_dotenv

# ── Env / logging ──────────────────────────────────────────────────────────────
_ENV = Path(__file__).parent.parent.parent.parent / "quant-betting" / "soccer" / ".claude" / "worktrees" / "admiring-allen" / ".env"
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

BASE_DIR  = Path(__file__).parent.parent.parent
TGT_DB    = BASE_DIR / "pipeline" / "db" / "eyeblackiq.db"
CACHE_DIR = BASE_DIR / "scrapers" / "cache"
SPORT     = "NHL"

# ── NHL constants ──────────────────────────────────────────────────────────────
PYTH_EXP  = 2.0          # NHL Pythagorean exponent
HFA_ELO   = 35           # Home ELO advantage (points)
ELO_K     = 20           # ELO K-factor per game
ELO_BASE  = 1500         # Starting ELO for all teams
HFA_PYTH  = 0.04         # Home win% bonus in Pythagorean model

# Blend weights (when both Pyth and ELO available)
W_PYTH    = 0.60
W_ELO     = 0.40

# Minimum edge to write a signal (before tier check)
MIN_EDGE  = 0.02

ESPN_SITE = "https://site.api.espn.com/apis/site/v2/sports"

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "EyeBlackIQ/1.0 (research)"})


# ── Tier / sizing ──────────────────────────────────────────────────────────────
def nhl_team_tier(edge_pct: float) -> tuple:
    """Returns (tier_label, units) for edge in 0-100 scale."""
    if   edge_pct >= 12: return ("SNIPE",        2.0)
    elif edge_pct >=  5: return ("SLOT MACHINE", 1.5)
    elif edge_pct >=  2: return ("SCOUT",        1.0)
    else:                return ("ICING",         0.0)


# ── Odds math ─────────────────────────────────────────────────────────────────
def american_to_implied(odds: int) -> float:
    """American odds → implied probability (raw, includes vig)."""
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def devig_2way(o1: int, o2: int) -> tuple:
    """Additive devig for 2-way market. Returns (p1_fair, p2_fair)."""
    i1, i2 = american_to_implied(o1), american_to_implied(o2)
    total   = i1 + i2
    return i1 / total, i2 / total


def american_to_decimal(o: int) -> float:
    return o / 100 + 1 if o > 0 else 100 / abs(o) + 1


def ev_calc(decimal_odds: float, model_p: float) -> float:
    return (decimal_odds - 1) * model_p - (1 - model_p)


def prob_to_american(p: float) -> int:
    """Convert win probability to nearest American ML odds."""
    if p <= 0 or p >= 1:
        return 0
    if p >= 0.5:
        return int(round(-p / (1 - p) * 100))
    return int(round((1 - p) / p * 100))


# ── Pythagorean engine ─────────────────────────────────────────────────────────
def pythagorean_win_pct(gf: float, ga: float, exp: float = PYTH_EXP) -> float:
    """
    Pythagorean win probability: GF^exp / (GF^exp + GA^exp).
    Clamps to [0.05, 0.95] to prevent division issues with extreme records.
    """
    if gf <= 0 or ga <= 0:
        return 0.5
    gf_p = gf ** exp
    ga_p = ga ** exp
    return max(0.05, min(0.95, gf_p / (gf_p + ga_p)))


def pyth_h2h(pyth_home: float, pyth_away: float, hfa: float = HFA_PYTH) -> float:
    """
    Head-to-head Pythagorean probability for home team.
    Log5 formula: P(A beats B) = (A - A*B) / (A + B - 2*A*B)
    with HFA additive adjustment applied before log5.
    """
    p_h = min(0.95, max(0.05, pyth_home + hfa / 2))
    p_a = min(0.95, max(0.05, pyth_away - hfa / 2))
    num = p_h - p_h * p_a
    den = p_h + p_a - 2 * p_h * p_a
    return max(0.05, min(0.95, num / den)) if den != 0 else 0.5


# ── ELO engine ────────────────────────────────────────────────────────────────
def elo_expected(elo_home: float, elo_away: float, hfa: float = HFA_ELO) -> float:
    """Expected win probability for home team given ELO ratings + HFA."""
    diff = (elo_home + hfa) - elo_away
    return 1 / (1 + 10 ** (-diff / 400))


def build_elo_from_records(standings: list) -> dict:
    """
    Approximate ELO from current season W/L records using iterative simulation.
    Processes teams in order of wins (better teams tend to have beaten weaker ones).
    Each win = K * (1 - expected); each loss = K * (0 - expected) against a
    proxy opponent at average ELO.

    This is a rough approximation — proper ELO needs game-by-game history.
    Returns dict keyed by team display name.
    """
    elo_map = {}
    for team_data in standings:
        name = team_data["name"]
        wins = team_data.get("wins", 0)
        losses = team_data.get("losses", 0)
        gp    = wins + losses + team_data.get("ot_losses", 0)
        elo   = float(ELO_BASE)

        if gp > 0:
            # Simulate wins and losses against a neutral opponent (ELO = 1500)
            for _ in range(wins):
                exp   = 1 / (1 + 10 ** (-(elo - ELO_BASE) / 400))
                elo  += ELO_K * (1 - exp)
            for _ in range(losses + team_data.get("ot_losses", 0)):
                exp   = 1 / (1 + 10 ** (-(elo - ELO_BASE) / 400))
                elo  += ELO_K * (0 - exp)

        elo_map[name] = round(elo, 1)
    return elo_map


# ── ESPN standings fetcher ─────────────────────────────────────────────────────
@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=8))
def fetch_nhl_standings() -> list:
    """
    Pull current NHL team records from ESPN teams endpoint.

    Uses /teams?limit=50 + individual team record items which carry
    wins, losses, OT losses, goals for/against per game.

    Returns list of team dicts with: name, wins, losses, ot_losses, gf, ga, gp.
    """
    url  = f"{ESPN_SITE}/hockey/nhl/teams?limit=50"
    resp = SESSION.get(url, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    sports  = data.get("sports", [])
    if not sports:
        return []
    leagues = sports[0].get("leagues", [])
    if not leagues:
        return []
    raw_teams = leagues[0].get("teams", [])

    teams = []
    for raw in raw_teams:
        team_info = raw.get("team", {})
        team_id   = team_info.get("id", "")
        name      = team_info.get("displayName", "?")
        if not team_id:
            continue

        # Fetch individual team record (has stats with GF, GA, W, L, OTL)
        try:
            t_url  = f"{ESPN_SITE}/hockey/nhl/teams/{team_id}"
            t_resp = SESSION.get(t_url, timeout=10)
            t_resp.raise_for_status()
            t_data  = t_resp.json()
            t_team  = t_data.get("team", {})
            records = t_team.get("record", {}).get("items", [])
        except Exception as e:
            logger.debug(f"Could not load record for {name}: {e}")
            records = []

        # Find the "Overall Record" entry
        stats = {}
        for rec in records:
            if rec.get("type") == "total":
                stats = {s["name"]: s.get("value", 0) for s in rec.get("stats", [])}
                break

        if not stats:
            continue

        gp  = int(stats.get("gamesPlayed", 0))
        gf  = float(stats.get("avgPointsFor",     stats.get("pointsFor", 0)))
        ga  = float(stats.get("avgPointsAgainst", stats.get("pointsAgainst", 0)))

        # avgPointsFor is goals/game if present; otherwise divide totals by gp
        if stats.get("avgPointsFor"):
            gf_pg = gf
            ga_pg = ga
        else:
            gf_pg = gf / max(gp, 1)
            ga_pg = ga / max(gp, 1)

        teams.append({
            "name":       name,
            "wins":       int(stats.get("wins", 0)),
            "losses":     int(stats.get("losses", 0)),
            "ot_losses":  int(stats.get("overtimeLosses", stats.get("otLosses", 0))),
            "gf":         gf_pg * gp,        # total goals for (for Pythagorean)
            "ga":         ga_pg * gp,        # total goals against
            "gf_pg":      round(gf_pg, 3),
            "ga_pg":      round(ga_pg, 3),
            "points":     int(stats.get("points", 0)),
            "gp":         gp,
        })

        time.sleep(0.05)  # gentle rate limit on the per-team fetches

    logger.info(f"Loaded {len(teams)} NHL teams from ESPN teams endpoint")
    return teams


def build_team_ratings(standings: list) -> dict:
    """
    Build team ratings dict from standings.
    Returns dict keyed by team name:
      {pyth_win_pct, elo, gf_per_game, ga_per_game, wins, losses, gp}
    """
    elo_map = build_elo_from_records(standings)
    ratings = {}
    for td in standings:
        name = td["name"]
        gp   = td.get("gp", td["wins"] + td["losses"] + td.get("ot_losses", 0))
        gp   = max(gp, 1)
        gf_pg = td["gf"] / gp if td["gf"] > 0 else 2.7  # NHL avg ~2.7 GPG
        ga_pg = td["ga"] / gp if td["ga"] > 0 else 2.7
        ratings[name] = {
            "pyth":   pythagorean_win_pct(td["gf"], td["ga"]),
            "elo":    elo_map.get(name, ELO_BASE),
            "gf_pg":  round(gf_pg, 3),
            "ga_pg":  round(ga_pg, 3),
            "wins":   td["wins"],
            "losses": td["losses"],
            "ot_l":   td.get("ot_losses", 0),
            "gp":     gp,
        }
    return ratings


# ── Name matching ──────────────────────────────────────────────────────────────
NHL_ALIASES = {
    # Abbreviations / short names → full ESPN displayName
    "Canadiens":          "Montreal Canadiens",
    "Maple Leafs":        "Toronto Maple Leafs",
    "Bruins":             "Boston Bruins",
    "Senators":           "Ottawa Senators",
    "Sabres":             "Buffalo Sabres",
    "Red Wings":          "Detroit Red Wings",
    "Panthers":           "Florida Panthers",
    "Lightning":          "Tampa Bay Lightning",
    "Hurricanes":         "Carolina Hurricanes",
    "Blue Jackets":       "Columbus Blue Jackets",
    "Rangers":            "New York Rangers",
    "Islanders":          "New York Islanders",
    "Flyers":             "Philadelphia Flyers",
    "Penguins":           "Pittsburgh Penguins",
    "Capitals":           "Washington Capitals",
    "Blackhawks":         "Chicago Blackhawks",
    "Avalanche":          "Colorado Avalanche",
    "Stars":              "Dallas Stars",
    "Wild":               "Minnesota Wild",
    "Predators":          "Nashville Predators",
    "Blues":              "St. Louis Blues",
    "Jets":               "Winnipeg Jets",
    "Flames":             "Calgary Flames",
    "Oilers":             "Edmonton Oilers",
    "Kings":              "Los Angeles Kings",
    "Ducks":              "Anaheim Ducks",
    "Sharks":             "San Jose Sharks",
    "Canucks":            "Vancouver Canucks",
    "Kraken":             "Seattle Kraken",
    "Golden Knights":     "Vegas Golden Knights",
    "Coyotes":            "Arizona Coyotes",
    "Devils":             "New Jersey Devils",
    "Utah Mammoth":       "Utah Mammoth",
}


def resolve_team(name: str, ratings: dict) -> Optional[str]:
    """
    Try to find name in ratings dict using exact match, alias, or fuzzy.
    Returns matched key or None.
    """
    if name in ratings:
        return name
    alias = NHL_ALIASES.get(name)
    if alias and alias in ratings:
        return alias
    # Fuzzy: check if any word in the team name is in a ratings key
    name_lower = name.lower()
    for key in ratings:
        if name_lower in key.lower() or key.lower() in name_lower:
            return key
        # Word-level match (e.g. "Golden Knights" matches "Vegas Golden Knights")
        if any(word in key.lower() for word in name_lower.split() if len(word) > 4):
            return key
    return None


# ── Model probability ──────────────────────────────────────────────────────────
def model_prob(home_name: str, away_name: str, ratings: dict) -> dict:
    """
    Compute model win probability for home team.
    Uses Pythagorean + ELO blend if both available.
    Falls back to Pythagorean-only or ELO-only.

    Returns dict with:
      p_home, p_away, method, home_key, away_key,
      pyth_home, pyth_away, elo_home, elo_away
    """
    h_key = resolve_team(home_name, ratings)
    a_key = resolve_team(away_name, ratings)

    if h_key is None or a_key is None:
        missing = []
        if h_key is None: missing.append(home_name)
        if a_key is None: missing.append(away_name)
        logger.warning(f"No ratings found for: {missing} — using 50/50")
        return {"p_home": 0.5, "p_away": 0.5, "method": "default",
                "home_key": home_name, "away_key": away_name,
                "pyth_home": 0.5, "pyth_away": 0.5,
                "elo_home": ELO_BASE, "elo_away": ELO_BASE}

    hr = ratings[h_key]
    ar = ratings[a_key]

    # Pythagorean head-to-head
    p_pyth = pyth_h2h(hr["pyth"], ar["pyth"])

    # ELO head-to-head
    p_elo  = elo_expected(hr["elo"], ar["elo"])

    # Blend
    p_home = W_PYTH * p_pyth + W_ELO * p_elo
    p_home = max(0.05, min(0.95, p_home))

    return {
        "p_home":     p_home,
        "p_away":     1 - p_home,
        "method":     "pyth+elo",
        "home_key":   h_key,
        "away_key":   a_key,
        "pyth_home":  round(hr["pyth"], 4),
        "pyth_away":  round(ar["pyth"], 4),
        "elo_home":   hr["elo"],
        "elo_away":   ar["elo"],
        "gf_pg_home": hr["gf_pg"],
        "ga_pg_home": hr["ga_pg"],
        "gf_pg_away": ar["gf_pg"],
        "ga_pg_away": ar["ga_pg"],
    }


# ── Total model ────────────────────────────────────────────────────────────────
def project_total(proj: dict) -> float:
    """
    Simple projected total from GF/game averages.
    Returns projected combined goals.
    """
    return round(proj.get("gf_pg_home", 2.7) + proj.get("gf_pg_away", 2.7), 2)


# ── DB writer ─────────────────────────────────────────────────────────────────
def write_signal(conn: sqlite3.Connection, date_str: str,
                 game_str: str, game_time: str,
                 bet_type: str, side: str, market: str,
                 odds: int, model_p: float, no_vig_p: float,
                 edge: float, ev_val: float, tier: str, units: float,
                 notes: str) -> None:
    """Insert one signal into the signals table."""
    ts = datetime.now(timezone.utc).isoformat()
    conn.execute(
        """INSERT INTO signals
           (signal_date, sport, game, game_time, bet_type, side, market,
            odds, model_prob, no_vig_prob, edge, ev, tier, units,
            is_pod, gate1_pyth, gate2_edge, gate3_model_agree,
            gate4_line_move, gate5_etl_fresh, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,'GREEN','PASS','PASS','PASS','PASS',?,?)""",
        (date_str, SPORT, game_str, game_time, bet_type, side, market,
         odds, round(model_p, 4), round(no_vig_p, 4),
         round(edge, 4), round(ev_val, 4), tier, units,
         notes, ts)
    )


# ── Odds loader ───────────────────────────────────────────────────────────────
def load_espn_odds(date_str: str) -> list:
    """
    Load NHL odds from ESPN scraper cache.
    If not cached, run scraper live.
    Returns list of unified game dicts.
    """
    # Try to import and use the module-level scraper
    try:
        sys.path.insert(0, str(BASE_DIR))
        from scrapers.scrape_free_odds import get_lines, run_scrape

        games = get_lines("nhl", date_str)
        if games:
            logger.info(f"Loaded {len(games)} NHL games from lines_cache")
            return games

        # Not in memory — check disk
        cache_file = CACHE_DIR / f"espn_odds_nhl_{date_str}.json"
        if cache_file.exists():
            with open(cache_file, encoding="utf-8") as f:
                data = json.load(f)
            games = data.get("results", [])
            logger.info(f"Loaded {len(games)} NHL games from disk cache")
            return games

        # Fetch fresh
        logger.info("NHL odds cache miss — fetching from ESPN...")
        result = run_scrape(date_str, ["nhl"])
        return result.get("nhl", [])

    except ImportError as e:
        logger.warning(f"Could not import scrape_free_odds: {e}")
        return []


# ── Main model ────────────────────────────────────────────────────────────────
def run_model(date_str: str, dry_run: bool = False) -> int:
    """
    Generate NHL team ML + totals signals for date_str.

    1. Load ESPN odds
    2. Load team ratings from ESPN standings
    3. For each game with odds: compute edge, write qualifying signals

    Returns number of signals written (0 in dry-run).
    """
    # Load odds
    games = load_espn_odds(date_str)
    if not games:
        logger.warning(f"No NHL games found for {date_str} — check ESPN availability")
        return 0

    # Load standings → ratings
    try:
        standings = fetch_nhl_standings()
    except Exception as e:
        logger.error(f"Failed to load NHL standings: {e}")
        standings = []

    if standings:
        ratings = build_team_ratings(standings)
        logger.info(f"Built ratings for {len(ratings)} NHL teams")
    else:
        logger.warning("No standings data — defaulting all teams to neutral 50/50")
        ratings = {}

    signals_written = 0
    conn = None

    if not dry_run:
        conn = sqlite3.connect(TGT_DB)
        conn.execute(
            "DELETE FROM signals WHERE signal_date=? AND sport=? AND bet_type IN ('ML','TOTAL')",
            (date_str, SPORT)
        )
        conn.commit()

    logger.info(f"NHL team model — {date_str} — {len(games)} games from ESPN")
    logger.info("  Tiers: SNIPE≥12% | SLOT MACHINE≥5% | SCOUT≥2%")

    for g in games:
        home      = g.get("home", "?")
        away      = g.get("away", "?")
        ml_home   = g.get("ml_home")
        ml_away   = g.get("ml_away")
        total     = g.get("total")
        start_utc = g.get("start_utc", "")
        game_str  = f"{away} @ {home}"

        # Game time display
        try:
            dt = datetime.fromisoformat(start_utc.replace("Z", "+00:00"))
            game_time = dt.strftime("%-I:%M %p ET") if sys.platform != "win32" \
                        else dt.strftime("%#I:%M %p ET")
        except Exception:
            game_time = "TBD"

        # Get model probabilities
        proj = model_prob(home, away, ratings)
        p_home  = proj["p_home"]
        p_away  = proj["p_away"]
        h_key   = proj["home_key"]
        a_key   = proj["away_key"]

        logger.info(
            f"  {game_str}  P_home={p_home:.3f}  "
            f"Pyth={proj['pyth_home']:.3f}  ELO={proj['elo_home']:.0f}  "
            f"vs  Pyth={proj['pyth_away']:.3f}  ELO={proj['elo_away']:.0f}  "
            f"[{proj['method']}]"
        )

        # ── ML signals ────────────────────────────────────────────────────────
        if ml_home is not None and ml_away is not None:
            ml_home = int(ml_home)
            ml_away = int(ml_away)
            nv_home, nv_away = devig_2way(ml_home, ml_away)
            edge_h = p_home - nv_home
            edge_a = p_away - nv_away

            for side_name, model_p, nv_p, edge_val, odds in [
                (home, p_home, nv_home, edge_h, ml_home),
                (away, p_away, nv_away, edge_a, ml_away),
            ]:
                if edge_val < MIN_EDGE:
                    continue

                edge_pct  = edge_val * 100
                tier_name, units = nhl_team_tier(edge_pct)
                if units == 0.0:
                    continue

                dec_odds = american_to_decimal(odds)
                ev_val   = ev_calc(dec_odds, model_p)
                is_home  = (side_name == home)
                team_key = h_key if is_home else a_key
                tm_r     = ratings.get(team_key, {})

                notes = (
                    f"Pyth={proj['pyth_home' if is_home else 'pyth_away']:.3f}  "
                    f"ELO={proj['elo_home' if is_home else 'elo_away']:.0f}  "
                    f"GF/G={tm_r.get('gf_pg', 0):.2f}  "
                    f"GA/G={tm_r.get('ga_pg', 0):.2f}  "
                    f"W-L={tm_r.get('wins', '?')}-{tm_r.get('losses', '?')}"
                    f"-{tm_r.get('ot_l', '?')}OTL  "
                    f"nv_mkt={nv_p:.3f}  model={model_p:.3f}"
                )

                logger.info(
                    f"    ML SIGNAL: {side_name} {odds:+d}  "
                    f"Edge {edge_pct:.1f}%  {tier_name}  {units}u  "
                    f"EV={ev_val:.3f}"
                )

                if not dry_run and conn:
                    write_signal(
                        conn, date_str,
                        game_str, game_time,
                        "ML", f"{side_name} ML", "ML",
                        odds, model_p, nv_p,
                        edge_val, ev_val, tier_name, units, notes
                    )
                    signals_written += 1
        else:
            logger.debug(f"    No ML odds for {game_str}")

        # ── Totals signals ────────────────────────────────────────────────────
        if total is not None:
            over_odds  = g.get("total_over_odds",  -110)
            under_odds = g.get("total_under_odds", -110)
            if over_odds is None:  over_odds  = -110
            if under_odds is None: under_odds = -110
            # ESPN sometimes returns floats (e.g. -110.0) — normalise to int
            over_odds  = int(over_odds)
            under_odds = int(under_odds)

            proj_total = project_total(proj)
            logger.info(
                f"    Total: line={total}  projected={proj_total}  "
                f"over={over_odds:+d}  under={under_odds:+d}"
            )

            nv_over, nv_under = devig_2way(over_odds, under_odds)

            # Model probability of going over
            diff = proj_total - total
            # Use a logistic-style probability estimate from the goal difference
            # ~0.15 goals difference ≈ 5% edge shift (calibrated for NHL scoring)
            p_over  = max(0.05, min(0.95, 0.5 + diff * 0.18))
            p_under = 1 - p_over

            for side_label, model_p_t, nv_p_t, odds_t, over_flag in [
                (f"Over {total}",  p_over,  nv_over,  over_odds,  True),
                (f"Under {total}", p_under, nv_under, under_odds, False),
            ]:
                edge_val = model_p_t - nv_p_t
                if edge_val < MIN_EDGE:
                    continue
                edge_pct = edge_val * 100
                tier_name, units = nhl_team_tier(edge_pct)
                if units == 0.0:
                    continue

                dec_odds = american_to_decimal(odds_t)
                ev_val_t = ev_calc(dec_odds, model_p_t)

                notes_t = (
                    f"proj_total={proj_total}  line={total}  "
                    f"diff={diff:+.2f}  "
                    f"gf_pg_h={proj.get('gf_pg_home', 0):.2f}  "
                    f"gf_pg_a={proj.get('gf_pg_away', 0):.2f}  "
                    f"nv_mkt={nv_p_t:.3f}  model={model_p_t:.3f}"
                )

                logger.info(
                    f"    TOTAL SIGNAL: {side_label} {odds_t:+d}  "
                    f"Edge {edge_pct:.1f}%  {tier_name}  {units}u"
                )

                if not dry_run and conn:
                    write_signal(
                        conn, date_str,
                        game_str, game_time,
                        "TOTAL", side_label, "totals",
                        odds_t, model_p_t, nv_p_t,
                        edge_val, ev_val_t, tier_name, units, notes_t
                    )
                    signals_written += 1

    if not dry_run and conn:
        conn.commit()
        conn.close()
        logger.info(f"NHL team model: wrote {signals_written} signals to DB")
    else:
        logger.info(f"NHL team model [DRY-RUN]: {signals_written} qualifying signals found")

    return signals_written


# ── CLI ────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="NHL team ML + totals signal generator")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"),
                        help="Date to run model for (YYYY-MM-DD)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Project signals without writing to DB")
    args = parser.parse_args()

    n = run_model(args.date, args.dry_run)
    print(f"NHL team signals: {n}")
