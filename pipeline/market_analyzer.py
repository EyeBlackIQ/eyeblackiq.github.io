"""
EyeBlackIQ — market_analyzer.py
Full market view pipeline — runs on ALL games regardless of edge.
Records model output for every game analyzed, enabling full transparency.

Writes to: /data/model_analyzed.json (append mode per date)

Usage:
  python pipeline/market_analyzer.py --date 2026-03-21
  python pipeline/market_analyzer.py --date 2026-03-21 --sport NCAA
"""
import json
import sqlite3
import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).parent.parent
DB_PATH       = BASE_DIR / "pipeline" / "db" / "eyeblackiq.db"
OUTPUT_PATH   = BASE_DIR / "data" / "model_analyzed.json"


def _load_existing() -> list:
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, encoding="utf-8") as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return []
    return []


def _write(data: list):
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def _get_signals_for_date(date_str: str, sport: Optional[str] = None) -> list:
    """Load all signals for a date from DB (not just edge-positive ones)."""
    if not DB_PATH.exists():
        logger.warning(f"DB not found at {DB_PATH}")
        return []
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        if sport:
            cur = conn.execute(
                """SELECT id, signal_date, sport, game, game_time, bet_type, side, market,
                          odds, model_prob, no_vig_prob, edge, ev, tier, units, is_pod
                   FROM signals
                   WHERE signal_date = ? AND sport LIKE ?
                   ORDER BY sport, edge DESC""",
                (date_str, f"%{sport.upper()}%")
            )
        else:
            cur = conn.execute(
                """SELECT id, signal_date, sport, game, game_time, bet_type, side, market,
                          odds, model_prob, no_vig_prob, edge, ev, tier, units, is_pod
                   FROM signals
                   WHERE signal_date = ?
                   ORDER BY sport, edge DESC""",
                (date_str,)
            )
        return [dict(r) for r in cur.fetchall()]


def _get_results_for_date(date_str: str) -> dict:
    """Load graded results for a date, keyed by signal_id."""
    if not DB_PATH.exists():
        return {}
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT signal_id, result, units_net FROM results WHERE signal_date = ?",
            (date_str,)
        )
        return {r["signal_id"]: dict(r) for r in cur.fetchall()}


def classify_tier(edge: float) -> str:
    """Classify edge into pick tier bucket."""
    e = (edge or 0) * 100
    if   e >= 12: return "T1_HIGH"
    elif e >=  5: return "T2_EDGE"
    elif e >=  2: return "T3_RADAR"
    elif e >   0: return "T4_THIN"
    else:         return "T5_NO_EDGE"


def analyze_date(date_str: str, sport: Optional[str] = None) -> list:
    """
    Analyze all signals for a date. Returns list of market analysis records.
    """
    signals  = _get_signals_for_date(date_str, sport)
    results  = _get_results_for_date(date_str)
    analyzed = []

    for sig in signals:
        result_row   = results.get(sig["id"], {})
        edge_val     = sig.get("edge") or 0
        pick_tier    = classify_tier(edge_val)
        generated_pick = (sig.get("units") or 0) > 0

        record = {
            "signal_id":       sig["id"],
            "date":            sig["signal_date"],
            "sport":           sig["sport"],
            "game":            sig["game"],
            "game_time":       sig.get("game_time"),
            "bet_type":        sig.get("bet_type"),
            "side":            sig.get("side"),
            "market":          sig.get("market"),
            "odds":            sig.get("odds"),
            "model_wp":        sig.get("model_prob"),
            "line_implied_wp": sig.get("no_vig_prob"),
            "edge_pct":        round(edge_val * 100, 2),
            "ev":              sig.get("ev"),
            "tier":            sig.get("tier"),
            "units":           sig.get("units"),
            "pick_tier":       pick_tier,
            "generated_pick":  generated_pick,
            "is_pod":          bool(sig.get("is_pod")),
            "result":          result_row.get("result"),
            "units_net":       result_row.get("units_net"),
            "graded":          bool(result_row),
            "analyzed_at":     datetime.now(timezone.utc).isoformat(),
        }
        analyzed.append(record)

    logger.info(f"Analyzed {len(analyzed)} signals for {date_str}" + (f" [{sport}]" if sport else ""))
    return analyzed


def run(date_str: str, sport: Optional[str] = None):
    """Run analysis and append to output file."""
    new_records = analyze_date(date_str, sport)
    existing    = _load_existing()

    # Remove any existing entries for this date+sport to avoid duplicates
    key_filter = {"date": date_str}
    if sport:
        key_filter["sport_contains"] = sport.upper()

    cleaned = [
        r for r in existing
        if not (
            r.get("date") == date_str and
            (not sport or sport.upper() in (r.get("sport") or "").upper())
        )
    ]

    merged = cleaned + new_records
    _write(merged)
    logger.info(f"Written {len(merged)} total records to {OUTPUT_PATH.name}")
    return new_records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EyeBlackIQ market analyzer")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--sport", default=None, help="Filter by sport: NCAA|MLB|NHL|SOCCER")
    args = parser.parse_args()
    records = run(args.date, args.sport)
    print(f"Analyzed {len(records)} signals for {args.date}")
    for r in records[:5]:
        sign = "+" if (r.get("edge_pct") or 0) >= 0 else ""
        print(f"  [{r['sport']}] {r['side']}  edge={sign}{r.get('edge_pct','?')}%  tier={r.get('pick_tier','?')}  graded={r.get('graded')}")
