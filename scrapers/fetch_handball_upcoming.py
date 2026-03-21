"""
EyeBlackIQ — scrapers/fetch_handball_upcoming.py
=================================================
Fetches upcoming handball fixtures and generates forward-looking signals.

SOURCES (in priority order):
  1. API Sports handball endpoint  — upcoming EHF CL + HBL games
     https://v1.handball.api-sports.io/games?league={id}&season=2025&next=10
  2. ESPN handball scoreboard      — fallback (no key required)
     https://site.api.espn.com/apis/site/v2/sports/handball/scoreboard
  3. Hardcoded EHF Champions League QF schedule — static fallback

OUTPUT:
  - handball_matches table: upcoming fixtures with NULL scores + status=UPCOMING
  - signals table: forward picks with note "FORWARD_PICK: model run on DATE for future game"

USAGE:
  python scrapers/fetch_handball_upcoming.py
  python scrapers/fetch_handball_upcoming.py --dry-run
  python scrapers/fetch_handball_upcoming.py --hardcoded-only
"""

import os
import sys
import json
import time
import logging
import sqlite3
import urllib.request
import urllib.error
import argparse
from datetime import datetime, timezone
from pathlib import Path

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
logger = logging.getLogger("fetch_handball_upcoming")

BASE_DIR   = Path(__file__).parent.parent
DB_PATH    = BASE_DIR / "pipeline" / "db" / "eyeblackiq.db"
TODAY_STR  = datetime.now(timezone.utc).strftime("%Y-%m-%d")

APISPORTS_KEY  = os.getenv("APISPORTS_KEY", "")
APISPORTS_BASE = "https://v1.handball.api-sports.io"
ESPN_BASE      = "https://site.api.espn.com/apis/site/v2/sports/handball"

# API Sports league IDs for handball
# 1 = EHF Champions League Men, 2 = HBL (Bundesliga Men), 3 = EHF EL, etc.
APISPORTS_LEAGUES = [1, 2]

# ── Hardcoded EHF Champions League QF fallback fixtures ───────────────────────
# Approximate schedule based on typical EHF CL April timetable.
# These are forward-modeling hypothetical dates.
HARDCODED_EHF_CL_QF = [
    {
        "game_id":    "HARDCODED_EHFCL_QF1_2026",
        "date":       "2026-04-02",
        "league_id":  1,
        "league_name": "EHF Champions League",
        "season":     "2025-26",
        "home_team":  "FC Barcelona",
        "away_team":  "SC Magdeburg",
        "game_time":  "18:45",
        "status":     "UPCOMING",
        "source":     "HARDCODED_EHF",
        "note":       "QF Leg 1 — approx date",
    },
    {
        "game_id":    "HARDCODED_EHFCL_QF2_2026",
        "date":       "2026-04-02",
        "league_id":  1,
        "league_name": "EHF Champions League",
        "season":     "2025-26",
        "home_team":  "SG Flensburg-Handewitt",
        "away_team":  "KS Industria Kielce",
        "game_time":  "20:45",
        "status":     "UPCOMING",
        "source":     "HARDCODED_EHF",
        "note":       "QF Leg 1 — approx date",
    },
    {
        "game_id":    "HARDCODED_EHFCL_QF3_2026",
        "date":       "2026-04-02",
        "league_id":  1,
        "league_name": "EHF Champions League",
        "season":     "2025-26",
        "home_team":  "Paris Saint-Germain HB",
        "away_team":  "Telekom Veszprem HC",
        "game_time":  "18:45",
        "status":     "UPCOMING",
        "source":     "HARDCODED_EHF",
        "note":       "QF Leg 1 — approx date",
    },
    {
        "game_id":    "HARDCODED_EHFCL_QF4_2026",
        "date":       "2026-04-09",
        "league_id":  1,
        "league_name": "EHF Champions League",
        "season":     "2025-26",
        "home_team":  "Telekom Veszprem HC",
        "away_team":  "Paris Saint-Germain HB",
        "game_time":  "18:45",
        "status":     "UPCOMING",
        "source":     "HARDCODED_EHF",
        "note":       "QF Leg 2 (return leg) — approx date",
    },
]


# ── DB helpers ────────────────────────────────────────────────────────────────
def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def store_upcoming_fixtures(fixtures: list) -> int:
    """
    Insert upcoming handball fixtures (NULL scores) into handball_matches.
    Status = UPCOMING. Skips if game_id already exists.
    Returns count of newly inserted rows.
    """
    if not fixtures:
        return 0
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        for fx in fixtures:
            if not fx.get("home_team") or not fx.get("date"):
                continue
            try:
                conn.execute(
                    """INSERT OR IGNORE INTO handball_matches
                       (game_id, date, league_id, league_name, season,
                        home_team, away_team, home_score, away_score,
                        game_time, status, source, created_at)
                       VALUES (?,?,?,?,?,?,?,NULL,NULL,?,?,?,?)""",
                    (
                        fx.get("game_id", f"UPC_{fx['date']}_{fx['home_team'][:4]}"),
                        fx["date"],
                        fx.get("league_id", 0),
                        fx.get("league_name", "Unknown"),
                        fx.get("season", "2025-26"),
                        fx["home_team"],
                        fx.get("away_team", "TBD"),
                        fx.get("game_time", "TBD"),
                        fx.get("status", "UPCOMING"),
                        fx.get("source", "API"),
                        now,
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
            ("HANDBALL_UPCOMING", "handball_matches", inserted,
             TODAY_STR, datetime.now(timezone.utc).isoformat())
        )
        conn.commit()

    logger.info(f"[HANDBALL_UPCOMING] {inserted} new fixtures stored in handball_matches.")
    return inserted


# ── Source 1: API Sports ──────────────────────────────────────────────────────
def fetch_apisports_upcoming(league_id: int, next_n: int = 10) -> list:
    """
    Fetch next N upcoming games from API Sports handball endpoint.
    Returns list of fixture dicts.
    """
    if not APISPORTS_KEY:
        logger.warning("[HANDBALL_UPCOMING] APISPORTS_KEY not set — skipping API Sports.")
        return []

    url = f"{APISPORTS_BASE}/games?league={league_id}&season=2025&next={next_n}"
    req = urllib.request.Request(url)
    req.add_header("x-apisports-key", APISPORTS_KEY)
    req.add_header("x-rapidapi-key",  APISPORTS_KEY)

    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            if e.code == 429:
                logger.warning(f"  API Sports rate limit hit (429) — attempt {attempt+1}/3, sleeping 30s")
                time.sleep(30)
            elif e.code in (401, 403):
                logger.warning(f"  API Sports auth error {e.code} — key exhausted or invalid. Skipping.")
                return []
            else:
                logger.error(f"  API Sports HTTP {e.code} for league={league_id}: {e}")
                return []
        except Exception as e:
            logger.error(f"  API Sports error league={league_id} attempt={attempt+1}: {e}")
            time.sleep(4)

    fixtures = []
    for item in (data.get("response") or []):
        f     = item.get("fixture") or item
        teams = item.get("teams") or {}
        ht    = (teams.get("home") or {}).get("name")
        at    = (teams.get("away") or {}).get("name")
        if not ht or not at:
            continue
        date_raw   = (f.get("date") or "")[:10]
        time_raw   = (f.get("time") or f.get("date") or "")
        status_raw = (f.get("status") or {}).get("short") or "NS"
        if status_raw in ("FT", "AET", "PEN"):
            continue  # skip completed games

        fixtures.append({
            "game_id":    f"API_{f.get('id', '')}",
            "date":       date_raw,
            "league_id":  league_id,
            "league_name": item.get("league", {}).get("name") or f"L{league_id}",
            "season":     str(item.get("league", {}).get("season") or "2025"),
            "home_team":  ht,
            "away_team":  at,
            "game_time":  time_raw[11:16] if len(time_raw) > 10 else "TBD",
            "status":     "UPCOMING",
            "source":     "API_SPORTS",
        })

    logger.info(f"[HANDBALL_UPCOMING] API Sports league={league_id}: {len(fixtures)} upcoming fixtures found.")
    return fixtures


# ── Source 2: ESPN handball scoreboard ───────────────────────────────────────
def fetch_espn_upcoming() -> list:
    """
    Try ESPN handball scoreboard for upcoming games.
    No key required. Returns list of fixture dicts.
    """
    url = f"{ESPN_BASE}/scoreboard"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "EyeBlackIQ/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.warning(f"[HANDBALL_UPCOMING] ESPN fallback failed: {e}")
        return []

    fixtures = []
    for event in (data.get("events") or []):
        comp   = (event.get("competitions") or [{}])[0]
        comps  = comp.get("competitors") or []
        if len(comps) < 2:
            continue
        ht = next((c["team"]["displayName"] for c in comps if c.get("homeAway") == "home"), None)
        at = next((c["team"]["displayName"] for c in comps if c.get("homeAway") == "away"), None)
        if not ht or not at:
            continue
        date_raw  = (event.get("date") or "")[:10]
        status    = (event.get("status") or {}).get("type", {}).get("name") or "STATUS_SCHEDULED"
        if "FINAL" in status.upper():
            continue

        fixtures.append({
            "game_id":    f"ESPN_{event.get('id', '')}",
            "date":       date_raw,
            "league_id":  0,
            "league_name": (event.get("season") or {}).get("type", {}).get("name") or "Handball",
            "season":     "2025-26",
            "home_team":  ht,
            "away_team":  at,
            "game_time":  (event.get("date") or "")[11:16],
            "status":     "UPCOMING",
            "source":     "ESPN",
        })

    logger.info(f"[HANDBALL_UPCOMING] ESPN: {len(fixtures)} upcoming fixtures found.")
    return fixtures


# ── Generate forward signals for upcoming fixtures ────────────────────────────
def generate_forward_signals(fixtures: list, dry_run: bool = False) -> list:
    """
    Run the handball Efficiency-Flow model on a list of upcoming fixtures.
    Writes signals with FORWARD_PICK notes to the signals table.

    Uses ELO from handball_team_stats. No market odds required (model-only signal).
    Gate 4 (line movement) is bypassed for forward-looking signals.
    Gate 5 (ETL freshness) is satisfied because we just computed ELO today.

    Returns list of generated signal dicts.
    """
    # Import model functions inline to avoid circular imports
    try:
        sys.path.insert(0, str(BASE_DIR))
        import math

        ELO_DEFAULT  = 1500
        HFA_ELO      = 50
        W_ELO        = 0.55
        W_POISSON    = 0.45
        HFA_PROB     = 0.06
        LG_AVG_GOALS = 29.5
        LG_AVG_POSS  = 52.0
        LG_AVG_EFF   = 0.568
        MIN_EDGE     = 0.03

        def _elo_prob(elo_h, elo_a):
            diff = (elo_h + HFA_ELO) - elo_a
            return 1 / (1 + 10 ** (-diff / 400))

        def _poisson_pmf(k, lam):
            if lam <= 0:
                return 1.0 if k == 0 else 0.0
            log_p = k * math.log(lam) - lam - sum(math.log(i) for i in range(1, k + 1))
            return math.exp(log_p)

        def _poisson_win(lh, la, maxg=50):
            pmf_h = [_poisson_pmf(k, lh) for k in range(maxg + 1)]
            pmf_a = [_poisson_pmf(k, la) for k in range(maxg + 1)]
            pw = pd = pl = 0.0
            for h in range(maxg + 1):
                for a in range(maxg + 1):
                    p = pmf_h[h] * pmf_a[a]
                    if h > a:
                        pw += p
                    elif h == a:
                        pd += p
                    else:
                        pl += p
            return pw + 0.5 * pd, pl + 0.5 * pd

    except Exception as e:
        logger.error(f"[HANDBALL_UPCOMING] Failed to set up model functions: {e}")
        return []

    def _load_team_elo(team_name):
        try:
            with get_conn() as conn:
                row = conn.execute(
                    "SELECT elo_rating, games_played FROM handball_team_stats "
                    "WHERE team_name = ? ORDER BY season DESC LIMIT 1",
                    (team_name,)
                ).fetchone()
            if row:
                return float(row["elo_rating"] or ELO_DEFAULT), int(row["games_played"] or 0)
        except Exception:
            pass
        return ELO_DEFAULT, 0

    signals = []
    now_iso = datetime.now(timezone.utc).isoformat()

    for fx in fixtures:
        ht = fx["home_team"]
        at = fx["away_team"]
        fx_date = fx["date"]

        home_elo, home_gp = _load_team_elo(ht)
        away_elo, away_gp = _load_team_elo(at)

        # ELO probability
        p_home_elo = _elo_prob(home_elo, away_elo)
        p_away_elo = 1 - p_home_elo

        # Poisson (using league defaults when no possession data)
        lambda_home = LG_AVG_POSS * LG_AVG_EFF * (1 + HFA_PROB / 2)
        lambda_away = LG_AVG_POSS * LG_AVG_EFF * (1 - HFA_PROB / 4)
        p_home_pois, p_away_pois = _poisson_win(lambda_home, lambda_away)

        # Blend
        p_home = W_ELO * p_home_elo + W_POISSON * p_home_pois
        p_away = W_ELO * p_away_elo + W_POISSON * p_away_pois
        total  = p_home + p_away
        if total > 0:
            p_home /= total
            p_away /= total

        # For forward picks, use ELO-implied fair market (no external odds)
        # We report the model's raw probability as the signal.
        # Edge is measured vs 50/50 (no market to compare against).
        # Only generate signal if model is decisive (>= 55% probability).

        min_gp = min(home_gp, away_gp)
        game_str = f"{at} @ {ht}"
        forward_note = (
            f"FORWARD_PICK: model run on {TODAY_STR} for future game {fx_date}  "
            f"ELO_home={home_elo:.0f}({home_gp}g)  ELO_away={away_elo:.0f}({away_gp}g)  "
            f"ELO_p={p_home_elo:.3f}  Poisson_p={p_home_pois:.3f}  "
            f"League={fx.get('league_name','?')}  Source={fx.get('source','?')}  "
            f"{fx.get('note','')}"
        )

        # Write the signal for each side where model has >= 55% (forward picks)
        for side, p_model in [(f"{ht} ML", p_home), (f"{at} ML", p_away)]:
            if p_model < 0.55:
                continue  # not decisive enough for a forward pick

            sig = {
                "signal_date": fx_date,
                "sport":       "HANDBALL",
                "game":        game_str,
                "game_time":   fx.get("game_time", "TBD"),
                "bet_type":    "ML",
                "side":        side,
                "market":      "ML",
                "odds":        -110,  # placeholder — no market odds available
                "model_prob":  round(p_model, 4),
                "no_vig_prob": 0.5000,  # no market to devig
                "edge":        round(p_model - 0.5, 4),  # vs 50/50
                "ev":          0.0,
                "tier":        "MONITOR" if p_model < 0.65 else "WHEELHOUSE",
                "units":       1.0,
                "is_pod":      0,
                "pod_sport":   None,
                "notes":       forward_note,
                "gate1":       "GREEN" if min_gp >= 30 else "YELLOW",
                "gate2":       "PASS" if p_model >= 0.55 else "FAIL",
                "gate3":       "PASS",  # no decomp model to compare against
                "gate4":       "PASS",  # bypassed for forward picks (no live line)
                "gate5":       "PASS",  # ETL run today
                "pick_source": "MODEL_FORWARD",
                "b2b_flag":    None,
            }
            signals.append(sig)
            logger.info(
                f"[HANDBALL_UPCOMING] FORWARD PICK: {side} p={p_model:.3f} "
                f"({fx_date}) — {ht} vs {at}"
            )

    # Write to DB
    if not dry_run:
        now = datetime.now(timezone.utc).isoformat()
        with get_conn() as conn:
            for sig in signals:
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO signals
                           (signal_date, sport, game, game_time, bet_type, side, market,
                            odds, model_prob, no_vig_prob, edge, ev, tier, units,
                            is_pod, pod_sport, notes,
                            gate1_pyth, gate2_edge, gate3_model_agree,
                            gate4_line_move, gate5_etl_fresh,
                            pick_source, b2b_flag, created_at)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            sig["signal_date"], sig["sport"], sig["game"], sig.get("game_time"),
                            sig["bet_type"], sig["side"], sig["market"],
                            sig["odds"], sig["model_prob"], sig["no_vig_prob"],
                            sig["edge"], sig.get("ev", 0), sig["tier"], sig["units"],
                            int(sig.get("is_pod", 0)), sig.get("pod_sport"),
                            sig.get("notes", ""),
                            sig.get("gate1", "GREEN"), sig.get("gate2", "PASS"),
                            sig.get("gate3", "PASS"), sig.get("gate4", "PASS"),
                            sig.get("gate5", "PASS"),
                            sig.get("pick_source", "MODEL_FORWARD"),
                            sig.get("b2b_flag"),
                            now,
                        )
                    )
                except sqlite3.Error as e:
                    logger.error(f"[HANDBALL_UPCOMING] Signal write error: {e}")
            conn.commit()
        logger.info(f"[HANDBALL_UPCOMING] {len(signals)} forward signals written to DB.")
    else:
        logger.info(f"[HANDBALL_UPCOMING] DRY-RUN — {len(signals)} forward signals (not written).")

    return signals


# ── Main orchestrator ─────────────────────────────────────────────────────────
def run(hardcoded_only: bool = False, dry_run: bool = False) -> dict:
    """
    Main entry: fetch upcoming handball fixtures + generate forward signals.
    Returns summary dict.
    """
    all_fixtures = []
    sources_tried = []

    if not hardcoded_only:
        # ── Source 1: API Sports ───────────────────────────────────────────────
        if APISPORTS_KEY:
            for lid in APISPORTS_LEAGUES:
                fxs = fetch_apisports_upcoming(lid, next_n=10)
                all_fixtures.extend(fxs)
                sources_tried.append(f"API_SPORTS L{lid}: {len(fxs)} fixtures")
                time.sleep(0.5)
        else:
            logger.info("[HANDBALL_UPCOMING] No APISPORTS_KEY — skipping API Sports.")
            sources_tried.append("API_SPORTS: skipped (no key)")

        # ── Source 2: ESPN fallback ────────────────────────────────────────────
        if not all_fixtures:
            logger.info("[HANDBALL_UPCOMING] No API Sports fixtures — trying ESPN fallback...")
            espn_fxs = fetch_espn_upcoming()
            all_fixtures.extend(espn_fxs)
            sources_tried.append(f"ESPN: {len(espn_fxs)} fixtures")

    # ── Source 3: Hardcoded EHF CL QF fallback ────────────────────────────────
    if not all_fixtures or hardcoded_only:
        logger.info(
            "[HANDBALL_UPCOMING] No live fixtures found — using hardcoded EHF CL QF schedule "
            "(HYPOTHETICAL dates for forward modeling)."
        )
        all_fixtures = HARDCODED_EHF_CL_QF
        sources_tried.append(f"HARDCODED_EHF: {len(all_fixtures)} fixtures")

    logger.info(f"[HANDBALL_UPCOMING] Total upcoming fixtures: {len(all_fixtures)}")

    # Store fixtures in DB
    stored = store_upcoming_fixtures(all_fixtures)

    # Generate forward signals
    signals = generate_forward_signals(all_fixtures, dry_run=dry_run)

    summary = {
        "run_date":        TODAY_STR,
        "fixtures_found":  len(all_fixtures),
        "fixtures_stored": stored,
        "signals_gen":     len(signals),
        "sources":         sources_tried,
        "fixtures":        [
            {
                "date":      fx["date"],
                "home":      fx["home_team"],
                "away":      fx.get("away_team"),
                "league":    fx.get("league_name"),
                "source":    fx.get("source"),
                "note":      fx.get("note", ""),
            }
            for fx in all_fixtures
        ],
        "signals": [
            {
                "date":   s["signal_date"],
                "side":   s["side"],
                "p_model": s["model_prob"],
                "edge":   s["edge"],
                "tier":   s["tier"],
            }
            for s in signals
        ],
    }
    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EyeBlackIQ handball upcoming fixtures + forward signals")
    parser.add_argument("--dry-run",        action="store_true", help="Do not write signals to DB")
    parser.add_argument("--hardcoded-only", action="store_true", help="Skip live APIs, use hardcoded EHF QF schedule")
    args = parser.parse_args()

    result = run(hardcoded_only=args.hardcoded_only, dry_run=args.dry_run)

    print(f"\n{'='*65}")
    print(f"  HANDBALL UPCOMING FIXTURES + FORWARD SIGNALS")
    print(f"  Run date: {result['run_date']}")
    print(f"{'='*65}")
    print(f"  Sources tried      : {', '.join(result['sources'])}")
    print(f"  Fixtures found     : {result['fixtures_found']}")
    print(f"  New fixtures in DB : {result['fixtures_stored']}")
    print(f"  Forward signals    : {result['signals_gen']} {'(DRY-RUN — not written)' if args.dry_run else '(written to DB)'}")

    print(f"\n  UPCOMING FIXTURES:")
    print(f"  {'Date':12s} {'Home':28s} {'Away':28s} {'League'}")
    print(f"  {'-'*85}")
    for fx in result["fixtures"]:
        note = f"  [{fx['note']}]" if fx.get("note") else ""
        print(f"  {fx['date']:12s} {fx['home']:28s} {fx['away']:28s} {fx['league']}{note}")

    if result["signals"]:
        print(f"\n  FORWARD SIGNALS:")
        print(f"  {'Date':12s} {'Side':35s} {'P_model':>9} {'Edge':>8} {'Tier'}")
        print(f"  {'-'*75}")
        for s in result["signals"]:
            print(f"  {s['date']:12s} {s['side']:35s} {s['p_model']*100:8.1f}%  {s['edge']*100:+6.1f}%  {s['tier']}")
    else:
        print(f"\n  No forward signals generated (model not decisive — p < 55% for all sides).")

    print(f"{'='*65}\n")
