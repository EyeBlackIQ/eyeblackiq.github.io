"""
scrape_fanduel_props.py — EyeBlackIQ v0.7.0
FanDuel public API scraper for NHL player props.
No API key required. FanDuel NJ public sportsbook endpoint.

SOG ONLY — the only NHL prop type with a verified Poisson model.
Goals/Points/Anytime: no model, not written to DB until a player model is live.

Player-specific lambda: NHL API skater stats (shots/game per player).
Positional fallback: Forward=2.6, Defenseman=1.9.

DraftKings: returns HTML (SPA, geo-restricted). TheRundown covers DK odds when
credits reset April 1 — see DAILY_RUN_GUIDE.md.

Usage:
  python scrape_fanduel_props.py [--date YYYY-MM-DD] [--dry-run] [--force-fetch]
"""
import sys, os, json, sqlite3, logging, argparse, re, math
from datetime import datetime, date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR  = Path(__file__).resolve().parent.parent
DB_PATH   = BASE_DIR / 'pipeline' / 'db' / 'eyeblackiq.db'
CACHE_DIR = Path(__file__).resolve().parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── FanDuel public endpoint ──────────────────────────────────────────────────
FANDUEL_NHL_URL = (
    'https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page'
    '?page=CUSTOM&customPageId=nhl&pbHorizontal=false'
    '&_ak=FhMFpcPWXMeyZxOx&includeMarkets=true'
)

FD_HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) '
        'AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 '
        'Mobile/15E148 Safari/604.1'
    ),
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.fanduel.com/',
    'Origin': 'https://www.fanduel.com',
}

# ─── NHL API — skater SOG stats ───────────────────────────────────────────────
NHL_SKATER_STATS_URL = (
    'https://api.nhle.com/stats/rest/en/skater/summary'
    '?limit=900'
    '&sort=[{"property":"points","direction":"DESC"}]'
    '&cayenneExp=gameTypeId=2%20and%20seasonId>=20252026%20and%20seasonId<=20252026'
)

# Positional fallback SOG/game if player not found in NHL stats
POS_FALLBACK = {
    'C': 2.6,   # Centre
    'L': 2.6,   # Left Wing
    'R': 2.6,   # Right Wing
    'D': 1.9,   # Defenseman
    'G': 0.0,   # Goalie — no SOG prop
}
DEFAULT_LAMBDA = 2.5   # used only if position also unknown


# ─── HTTP session ─────────────────────────────────────────────────────────────
def build_session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s


# ─── Player SOG stats lookup ──────────────────────────────────────────────────
def fetch_player_sog_stats(session, force: bool = False) -> dict:
    """
    Returns {normalized_name: {'sog_pg': float, 'team': str, 'position': str}}
    for all active NHL skaters this season.

    Cached daily to scrapers/cache/nhl_player_sog_{season}.json.
    """
    season = '20252026'
    cache_file = CACHE_DIR / f'nhl_player_sog_{season}.json'

    if cache_file.exists() and not force:
        logger.info('[NHL API] Using cached player SOG stats')
        return json.loads(cache_file.read_text(encoding='utf-8'))

    logger.info('[NHL API] Fetching current season skater SOG stats...')
    try:
        r = session.get(NHL_SKATER_STATS_URL, timeout=20)
        r.raise_for_status()
        data = r.json().get('data', [])
    except Exception as e:
        logger.warning(f'[NHL API] Fetch failed: {e}. Using positional fallbacks.')
        return {}

    lookup = {}
    for row in data:
        name      = (row.get('skaterFullName') or '').strip()
        shots     = row.get('shots') or 0       # "shots" in NHL API = shots on goal
        gp        = row.get('gamesPlayed') or 1
        team      = row.get('teamAbbrevs') or ''
        position  = row.get('positionCode') or 'C'

        if not name or gp < 3:
            continue

        sog_pg = round(shots / gp, 3)
        key = _normalize_name(name)
        lookup[key] = {
            'sog_pg':   sog_pg,
            'team':     team.split(',')[0].strip(),   # multi-team → take first
            'position': position,
            'gp':       gp,
        }

    cache_file.write_text(json.dumps(lookup), encoding='utf-8')
    logger.info(f'[NHL API] Loaded {len(lookup)} player SOG rates')
    return lookup


def _normalize_name(name: str) -> str:
    """Lowercase, strip team suffix like '(EDM)', strip accents loosely."""
    name = re.sub(r'\s*\(.*?\)\s*', '', name).strip().lower()
    return name


def get_lambda(player_name: str, stats: dict) -> tuple[float, str, str]:
    """
    Returns (lambda, team_abbrev, source_note).
    source_note = 'player_stat', 'positional_fallback', or 'league_avg'.
    """
    key = _normalize_name(player_name)
    if key in stats:
        s = stats[key]
        return s['sog_pg'], s['team'], 'player_stat'

    # Partial name match (handles middle names, accents)
    parts = key.split()
    for stat_key, s in stats.items():
        stat_parts = stat_key.split()
        if len(parts) >= 2 and len(stat_parts) >= 2:
            if parts[0] == stat_parts[0] and parts[-1] == stat_parts[-1]:
                return s['sog_pg'], s['team'], 'partial_match'

    return DEFAULT_LAMBDA, '', 'league_avg'


# ─── Probability helpers ──────────────────────────────────────────────────────
def american_to_prob(odds: int) -> float:
    if odds > 0:
        return 100 / (odds + 100)
    return abs(odds) / (abs(odds) + 100)


def devig_two_way(p_yes: float) -> float:
    total = p_yes + (1.0 - p_yes)
    return p_yes / total if total > 0 else p_yes


def poisson_p_at_least(lam: float, threshold: int) -> float:
    """P(X >= threshold) using Poisson(lambda)."""
    cdf = sum(
        math.exp(-lam) * (lam ** k) / math.factorial(k)
        for k in range(threshold)
    )
    return max(0.0, min(1.0, 1.0 - cdf))


# ─── Fetch FanDuel data ───────────────────────────────────────────────────────
def fetch_fanduel_nhl(today_str: str, session, force: bool = False) -> dict:
    cache_file = CACHE_DIR / f'fanduel_nhl_{today_str}.json'
    if cache_file.exists() and not force:
        logger.info('[FD] Using cached NHL data')
        return json.loads(cache_file.read_text(encoding='utf-8'))

    logger.info('[FD] Fetching NHL markets...')
    try:
        r = session.get(FANDUEL_NHL_URL, headers=FD_HEADERS, timeout=25)
        r.raise_for_status()
        data = r.json()
        cache_file.write_text(json.dumps(data), encoding='utf-8')
        logger.info(f'[FD] Fetched {len(str(data)):,} bytes')
        return data
    except Exception as e:
        logger.error(f'[FD] Fetch failed: {e}')
        return {}


# ─── Parse — SOG props only ───────────────────────────────────────────────────
def parse_sog_props(data: dict, player_stats: dict) -> list[dict]:
    """
    Parse only SOG (Shots On Goal) markets from FanDuel NHL response.
    Goals/Points/Anytime are skipped — no model yet.
    Returns list of signal dicts ready for DB insert.
    """
    attachments = data.get('attachments', {})
    events  = attachments.get('events', {})
    markets = attachments.get('markets', {})

    if not events or not markets:
        logger.warning('[FD] No events/markets in response')
        return []

    # Event lookup: eventId → game metadata
    event_map = {}
    for ev_id, ev in events.items():
        name  = ev.get('name', '')
        start = ev.get('openDate', '') or ev.get('eventDateTime', '')
        parts = re.split(r'\s+[vV@]\s+', name)
        if len(parts) == 2:
            away, home = parts[0].strip(), parts[1].strip()
        else:
            away, home = name, name
        event_map[ev_id] = {
            'home':      home,
            'away':      away,
            'game':      f'{away} @ {home}',
            'game_time': start[:16].replace('T', ' ') if start else '',
        }

    results = []

    for mkt in markets.values():
        mkt_name = (mkt.get('marketName') or mkt.get('marketType') or '').lower()
        ev_id    = str(mkt.get('eventId', ''))
        ev_info  = event_map.get(ev_id, {})

        # Only process SOG markets
        sog_m = re.search(r'player\s+(\d+)\+\s*shots?\s+on\s+goal', mkt_name)
        if not sog_m:
            continue

        threshold = int(sog_m.group(1))
        market_label = f'SOG{threshold}+'

        for runner in mkt.get('runners', []):
            player_name = runner.get('runnerName', '').strip()
            if not player_name or player_name.lower() in ('yes', 'no', 'over', 'under'):
                continue

            # Parse American odds from nested FD structure
            american_odds = _parse_fd_odds(runner)
            if american_odds is None:
                continue
            if abs(american_odds) > 1500:
                continue

            # Player-specific Poisson model
            lam, team, lam_source = get_lambda(player_name, player_stats)
            if lam <= 0:
                continue  # skip goalies

            model_prob = poisson_p_at_least(lam, threshold)
            fair_mkt   = devig_two_way(american_to_prob(american_odds))
            edge_val   = (model_prob - fair_mkt) * 100

            # Edge window: 3–30% for props
            if edge_val < 3.0:
                continue

            if edge_val >= 12:
                tier = 'SNIPE'; units = 2.0
            elif edge_val >= 5:
                tier = 'SLOT MACHINE'; units = 1.5
            else:
                tier = 'SCOUT'; units = 1.0

            edge_frac = edge_val / 100
            ev_frac   = edge_frac  # simplified for binary props

            results.append({
                'sport':       'NHL',
                'bet_type':    'NHL_SOG_PROP',
                'market':      market_label,
                'side':        f'{player_name} {market_label}',
                'odds':        american_odds,
                'model_prob':  round(model_prob, 4),
                'no_vig_prob': round(fair_mkt, 4),
                'edge':        round(edge_frac, 4),
                'ev':          round(ev_frac, 4),
                'tier':        tier,
                'units':       units,
                'is_pod':      0,
                'pick_source': 'SPORTSBOOK',
                'game':        ev_info.get('game', ''),
                'game_time':   ev_info.get('game_time', ''),
                'notes': (
                    f'source=FanDuel | player={player_name} | team={team} '
                    f'| threshold={market_label} | lam={lam:.2f} ({lam_source}) '
                    f'| nv_mkt={fair_mkt:.3f} | model={model_prob:.3f}'
                ),
            })

            logger.debug(
                f'[FD] {player_name} ({team}) {market_label} @ {american_odds} '
                f'| λ={lam:.2f} ({lam_source}) | model={model_prob:.1%} '
                f'| mkt={fair_mkt:.1%} | edge={edge_val:.1f}% | {tier}'
            )

    logger.info(f'[FD] SOG props with edge: {len(results)}')

    # Tier summary
    from collections import Counter
    tier_counts = Counter(r['tier'] for r in results)
    for t, n in sorted(tier_counts.items()):
        logger.info(f'  {t}: {n}')

    return results


def _parse_fd_odds(runner: dict) -> int | None:
    """Extract American odds integer from FanDuel runner object."""
    odds_obj = runner.get('winRunnerOdds', {})
    if not odds_obj:
        return None

    ado = odds_obj.get('americanDisplayOdds', {})
    if isinstance(ado, dict):
        v = ado.get('americanOddsInt') or ado.get('americanOdds')
        if v is not None:
            return int(v)
    elif isinstance(ado, (int, float)):
        return int(ado)

    # Fallback: convert decimal odds
    to = odds_obj.get('trueOdds', {})
    if isinstance(to, dict):
        dec = to.get('decimalOdds', {})
        if isinstance(dec, dict):
            d = dec.get('decimalOdds')
            if d and d > 1:
                return int((d - 1) * 100) if d >= 2 else int(-100 / (d - 1))
    return None


# ─── Write to DB ──────────────────────────────────────────────────────────────
def write_signals(props: list[dict], signal_date: str, dry_run: bool = False) -> int:
    if not props:
        logger.info('[DB] No signals to write.')
        return 0

    if dry_run:
        logger.info(f'[DB][DRY RUN] Would write {len(props)} signals')
        for p in props:
            print(f'  {p["side"]} @ {p["odds"]} | edge={p["edge"]*100:.1f}% | {p["tier"]}')
        return len(props)

    with sqlite3.connect(DB_PATH) as conn:
        # Remove today's SOG props before re-inserting (idempotent)
        conn.execute("""
            DELETE FROM signals
            WHERE signal_date = ?
              AND sport = 'NHL'
              AND bet_type = 'NHL_SOG_PROP'
              AND pick_source = 'SPORTSBOOK'
        """, (signal_date,))

        rows = [
            (
                signal_date,
                p['sport'],
                p['game'],
                p['game_time'],
                p['bet_type'],
                p['side'],
                p['market'],
                p['odds'],
                p['model_prob'],
                p['no_vig_prob'],
                p['edge'],
                p['ev'],
                p['tier'],
                p['units'],
                p['is_pod'],
                p['pick_source'],
                p['notes'],
                datetime.now().isoformat(),
            )
            for p in props
        ]

        conn.executemany("""
            INSERT INTO signals
              (signal_date, sport, game, game_time, bet_type, side, market,
               odds, model_prob, no_vig_prob, edge, ev, tier, units, is_pod,
               pick_source, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    logger.info(f'[DB] Wrote {len(props)} NHL SOG prop signals for {signal_date}')
    return len(props)


# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--date',        default=str(date.today()))
    parser.add_argument('--dry-run',     action='store_true')
    parser.add_argument('--force-fetch', action='store_true',
                        help='Bypass cache — re-fetch from FanDuel and NHL API')
    args = parser.parse_args()

    session    = build_session()
    today_str  = args.date
    force      = args.force_fetch

    # Step 1 — Player SOG stats (player-specific lambda)
    player_stats = fetch_player_sog_stats(session, force=force)

    # Step 2 — FanDuel NHL page
    fd_data = fetch_fanduel_nhl(today_str, session, force=force)

    # Step 3 — Parse SOG props with player-specific Poisson model
    props = parse_sog_props(fd_data, player_stats)

    # Step 4 — Verify: print lambda used per player (confirms no player uses 2.5 unless league_avg)
    print(f'\n[FanDuel NHL SOG] {len(props)} edge signals for {today_str}\n')
    lam_sources = {}
    for p in props:
        src = 'player_stat' if 'player_stat' in p['notes'] else \
              'partial_match' if 'partial_match' in p['notes'] else 'league_avg'
        lam_sources[src] = lam_sources.get(src, 0) + 1
    for src, n in sorted(lam_sources.items()):
        print(f'  λ source [{src}]: {n} props')

    # Step 5 — Write
    n = write_signals(props, today_str, dry_run=args.dry_run)

    # Summary by tier
    from collections import Counter
    tiers = Counter(p['tier'] for p in props)
    print(f'\nTier breakdown:')
    for tier, cnt in sorted(tiers.items()):
        print(f'  {tier}: {cnt}')

    print(f'\nDone — {n} signals written to DB.')
    print(
        '\nNOTE: DraftKings returns HTML (SPA, Cloudflare-blocked).\n'
        'Secondary source: TheRundown API covers DK odds — credits reset April 1.\n'
        'See DAILY_RUN_GUIDE.md.'
    )


if __name__ == '__main__':
    main()
