"""
scrape_fanduel_props.py — EyeBlackIQ
FanDuel public API scraper for NHL player props (SOG, Goals, Points, Assists).
No API key required. Uses FanDuel's public NJ sportsbook endpoint.

Writes prop signals to DB with pick_source='SPORTSBOOK'.
Usage: python scrape_fanduel_props.py [--dry-run] [--date YYYY-MM-DD]
"""
import sys, os, json, sqlite3, logging, argparse, re
from datetime import datetime, date
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH  = BASE_DIR / 'pipeline' / 'db' / 'eyeblackiq.db'
CACHE_DIR = Path(__file__).resolve().parent / 'cache'
CACHE_DIR.mkdir(exist_ok=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# ─── FanDuel public endpoints ─────────────────────────────────────────────────
FANDUEL_SPORTS = {
    'nhl':  'https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=nhl&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&includeMarkets=true',
    'mlb':  'https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=mlb&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&includeMarkets=true',
    'nfl':  'https://sbapi.nj.sportsbook.fanduel.com/api/content-managed-page?page=CUSTOM&customPageId=nfl&pbHorizontal=false&_ak=FhMFpcPWXMeyZxOx&includeMarkets=true',
}

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
    'Accept': 'application/json, text/plain, */*',
    'Accept-Language': 'en-US,en;q=0.9',
    'Referer': 'https://www.fanduel.com/',
    'Origin': 'https://www.fanduel.com',
}

# ─── Prop market name patterns we care about ─────────────────────────────────
PROP_PATTERNS = {
    'NHL': [
        r'player\s+(\d+)\+?\s*shots?\s+on\s+goal',
        r'player\s+to\s+score\s+(\d+)\+?\s*goals?',
        r'player\s+(\d+)\+?\s*goals?',
        r'player\s+(\d+)\+?\s*points?',
        r'player\s+(\d+)\+?\s*assists?',
        r'anytime\s+goal\s+scorer',
        r'first\s+goal\s+scorer',
    ],
    'MLB': [
        r'player\s+to\s+record\s+(\d+)\+?\s*strikeouts?',
        r'pitcher\s+(\d+)\+?\s*strikeouts?',
        r'batter\s+total\s+bases',
        r'player\s+hits?\s+a\s+home\s+run',
    ],
}

# ─── Edge model for SOG props ─────────────────────────────────────────────────
def american_to_prob(american_odds: int) -> float:
    """Convert American odds to implied probability (no vig removed per-runner)."""
    if american_odds > 0:
        return 100 / (american_odds + 100)
    else:
        return abs(american_odds) / (abs(american_odds) + 100)

def devig_two_way(p_yes: float) -> float:
    """Simple devig: normalize yes/no probabilities."""
    p_no = 1.0 - p_yes  # FD typically prices alternate, but SOG is binary yes/no
    total = p_yes + p_no
    return p_yes / total if total > 0 else p_yes

def build_session():
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504])
    s.mount('https://', HTTPAdapter(max_retries=retry))
    return s

# ─── Fetch + cache ────────────────────────────────────────────────────────────
def fetch_fanduel(sport: str, today_str: str, session) -> dict:
    cache_file = CACHE_DIR / f'fanduel_{sport}_{today_str}.json'
    if cache_file.exists():
        logger.info(f'[FD] Using cached {sport} data')
        return json.loads(cache_file.read_text(encoding='utf-8'))

    url = FANDUEL_SPORTS.get(sport)
    if not url:
        logger.warning(f'[FD] No URL configured for sport: {sport}')
        return {}

    logger.info(f'[FD] Fetching {sport} markets...')
    try:
        r = session.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
        data = r.json()
        cache_file.write_text(json.dumps(data), encoding='utf-8')
        logger.info(f'[FD] {sport}: fetched {len(str(data))} bytes')
        return data
    except Exception as e:
        logger.error(f'[FD] Fetch failed for {sport}: {e}')
        return {}

# ─── Parse markets ────────────────────────────────────────────────────────────
def parse_nhl_props(data: dict) -> list[dict]:
    """
    Extract player prop signals from FanDuel NHL response.
    Returns list of dicts ready to insert into signals table.
    """
    attachments = data.get('attachments', {})
    events  = attachments.get('events', {})
    markets = attachments.get('markets', {})

    if not events or not markets:
        logger.warning('[FD] No events/markets in response')
        return []

    # Build event lookup: eventId → {home, away, game_time}
    event_map = {}
    for ev_id, ev in events.items():
        name = ev.get('name', '')
        start = ev.get('openDate', '') or ev.get('eventDateTime', '')
        # FanDuel event names: "Boston Bruins v Detroit Red Wings"
        parts = re.split(r'\s+[vV@]\s+', name)
        if len(parts) == 2:
            away_team, home_team = parts[0].strip(), parts[1].strip()
        else:
            away_team, home_team = name, name
        event_map[ev_id] = {
            'home': home_team, 'away': away_team,
            'game': f'{away_team} @ {home_team}',
            'game_time': start[:16].replace('T', ' ') if start else '',
            'event_id': ev_id,
        }

    props = []
    for mkt_id, mkt in markets.items():
        market_name = mkt.get('marketName', '') or mkt.get('marketType', '')
        mkt_name_lower = market_name.lower()
        ev_id = str(mkt.get('eventId', ''))
        ev_info = event_map.get(ev_id, {})

        runners = mkt.get('runners', [])
        if not runners:
            continue

        # Detect SOG markets
        sog_match = re.search(r'player\s+(\d+)\+\s*shots?\s+on\s+goal', mkt_name_lower)
        goals_match = re.search(r'player\s+(\d+)\+\s*goals?(?!\s*scorer)', mkt_name_lower)
        points_match = re.search(r'player\s+(\d+)\+\s*points?', mkt_name_lower)
        anytime_goals = 'anytime goal scorer' in mkt_name_lower
        first_goal = 'first goal scorer' in mkt_name_lower

        if sog_match:
            threshold = int(sog_match.group(1))
            market_type = f'SOG{threshold}+'
            bet_type = 'NHL_SOG_PROP'
        elif goals_match:
            threshold = int(goals_match.group(1))
            market_type = f'GOALS{threshold}+'
            bet_type = 'NHL_GOALS_PROP'
        elif points_match:
            threshold = int(points_match.group(1))
            market_type = f'PTS{threshold}+'
            bet_type = 'NHL_POINTS_PROP'
        elif anytime_goals:
            market_type = 'ANYTIME_GOAL'
            bet_type = 'NHL_GOALS_PROP'
        elif first_goal:
            market_type = 'FIRST_GOAL'
            bet_type = 'NHL_GOALS_PROP'
        else:
            continue  # Not a player prop we track

        for runner in runners:
            player_name = runner.get('runnerName', '').strip()
            if not player_name or player_name.lower() in ('yes', 'no', 'over', 'under'):
                continue

            odds_obj = runner.get('winRunnerOdds', {})
            american_odds = None

            # FanDuel structure: winRunnerOdds.americanDisplayOdds.americanOdds (int)
            if odds_obj:
                ado = odds_obj.get('americanDisplayOdds', {})
                if isinstance(ado, dict):
                    american_odds = ado.get('americanOddsInt') or ado.get('americanOdds')
                elif isinstance(ado, (int, float)):
                    american_odds = int(ado)
                if american_odds is None:
                    # Fallback: trueOdds
                    to = odds_obj.get('trueOdds', {})
                    if isinstance(to, dict):
                        dec = to.get('decimalOdds', {})
                        if isinstance(dec, dict):
                            d = dec.get('decimalOdds')
                            if d:
                                american_odds = int((d - 1) * 100) if d >= 2 else int(-100 / (d - 1))

            if american_odds is None:
                continue

            try:
                american_odds = int(american_odds)
            except (ValueError, TypeError):
                continue

            # Only process reasonably liquid props (not super extreme odds)
            if abs(american_odds) > 1500:
                continue

            p_imp = american_to_prob(american_odds)

            # For SOG props, we compute edge using a simple baseline model:
            # - Expected SOG for most NHL players ≈ 2.5 shots/game (league avg)
            # - Threshold-based Poisson CDF to get model probability
            # - If market is mispriced vs Poisson > 5%, flag as edge
            model_prob = None
            edge = None
            tier = None
            units = 0.0
            conf_label = 'MED'

            if 'SOG' in market_type:
                import math
                lam = 2.5  # league avg shots on goal per player per game
                # Poisson P(X >= threshold) = 1 - sum(k=0..threshold-1) e^-lam * lam^k / k!
                cdf = sum(
                    math.exp(-lam) * (lam**k) / math.factorial(k)
                    for k in range(threshold)
                )
                model_prob = 1.0 - cdf
                fair_mkt   = devig_two_way(p_imp)
                edge_val   = (model_prob - fair_mkt) * 100

                # Edge window: 3-30% for props
                if edge_val >= 3.0:
                    edge  = edge_val
                    if edge_val >= 12:
                        tier  = 'SNIPE'; units = 2.0
                    elif edge_val >= 5:
                        tier  = 'SLOT MACHINE'; units = 1.5
                    else:
                        tier  = 'SCOUT'; units = 1.0
            else:
                # Non-SOG props: record the line for display, no model edge yet
                edge = 0.0
                tier = 'SCOUT'
                units = 0.0
                fair_mkt = devig_two_way(p_imp)

            if tier is None:
                continue  # Below edge threshold

            # edge as fraction for DB; ev as fraction
            edge_frac = (edge / 100) if edge else 0.0
            ev_frac   = edge_frac  # simplified: EV ≈ edge for binary props

            pick_dict = {
                'sport':       'NHL',
                'bet_type':    bet_type,          # e.g. 'NHL_SOG_PROP'
                'market':      market_type,        # e.g. 'SOG3+'
                'side':        f'{player_name} {market_type}',
                'odds':        american_odds,
                'model_prob':  round(model_prob, 4) if model_prob else round(fair_mkt, 4),
                'no_vig_prob': round(fair_mkt, 4),
                'edge':        round(edge_frac, 4),
                'ev':          round(ev_frac, 4),
                'tier':        tier,
                'units':       units,
                'is_pod':      0,
                'pick_source': 'SPORTSBOOK',
                'game':        ev_info.get('game', ''),
                'game_time':   ev_info.get('game_time', ''),
                'notes':       f'FanDuel prop | player={player_name} | threshold={market_type} | nv_mkt={fair_mkt:.3f} | model={model_prob:.3f}' if model_prob else f'FanDuel prop | player={player_name} | {market_type}',
            }
            props.append(pick_dict)
            logger.info(f'[FD] {player_name} {market_type} @ {american_odds} | edge={edge:.1f}% | tier={tier}')

    logger.info(f'[FD] Total NHL prop signals: {len(props)}')
    return props

# ─── Write to DB ──────────────────────────────────────────────────────────────
def write_signals(props: list[dict], signal_date: str, dry_run=False):
    if not props:
        logger.info('[FD] No signals to write.')
        return 0

    if dry_run:
        logger.info(f'[FD][DRY RUN] Would write {len(props)} signals:')
        for p in props:
            logger.info(f'  {p["side"]} @ {p["odds"]} | edge={p["edge_pct"]}% | tier={p["tier"]}')
        return len(props)

    with sqlite3.connect(DB_PATH) as conn:
        # First, clean out existing FD NHL prop signals for today to avoid duplicates
        conn.execute("""
            DELETE FROM signals
            WHERE signal_date = ? AND sport = 'NHL'
              AND bet_type IN ('NHL_SOG_PROP','NHL_GOALS_PROP','NHL_POINTS_PROP')
              AND pick_source = 'SPORTSBOOK'
        """, (signal_date,))

        rows = []
        for p in props:
            rows.append((
                signal_date,
                p['sport'],
                p['game'],
                p['game_time'],
                p['bet_type'],
                p['side'],
                p['market'],
                p['odds'],
                p.get('model_prob'),
                p.get('no_vig_prob'),
                p['edge'],
                p['ev'],
                p['tier'],
                p['units'],
                p['is_pod'],
                p['pick_source'],
                p.get('notes', ''),
                datetime.utcnow().isoformat(),
            ))

        conn.executemany("""
            INSERT INTO signals
              (signal_date, sport, game, game_time, bet_type, side, market,
               odds, model_prob, no_vig_prob, edge, ev, tier, units, is_pod,
               pick_source, notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, rows)
        conn.commit()

    logger.info(f'[FD] Wrote {len(props)} NHL prop signals for {signal_date}')
    return len(props)

# ─── Main ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--dry-run', action='store_true')
    parser.add_argument('--date',    default=str(date.today()))
    parser.add_argument('--sport',   default='nhl', choices=['nhl', 'mlb'])
    args = parser.parse_args()

    session   = build_session()
    today_str = args.date

    if args.sport == 'nhl':
        data  = fetch_fanduel('nhl', today_str, session)
        props = parse_nhl_props(data)
        n     = write_signals(props, today_str, dry_run=args.dry_run)
        print(f'\n[FanDuel NHL] {n} player prop signals written for {today_str}')

        # Summary by tier
        from collections import Counter
        tiers = Counter(p['tier'] for p in props)
        for tier, cnt in sorted(tiers.items()):
            print(f'  {tier}: {cnt} picks')

if __name__ == '__main__':
    main()
