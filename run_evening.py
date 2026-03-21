"""
EyeBlackIQ — run_evening.py
Evening runner: fetch results -> grade -> update records -> rebuild results page -> git push.

Usage:
  python run_evening.py                      # Today
  python run_evening.py --date 2026-03-21
  python run_evening.py --date 2026-03-21 --dry-run

--dry-run: Skip git push.
"""
import argparse
import logging
import json
import os
import sys
import subprocess
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-7s %(message)s"
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent


def run_cmd(label: str, cmd: list, cwd=None) -> bool:
    logger.info(f"  >>> {label}")
    try:
        r = subprocess.run(cmd, capture_output=False, text=True, cwd=cwd or BASE_DIR)
        return r.returncode == 0
    except Exception as e:
        logger.error(f"  ERROR: {label} — {e}")
        return False


def update_results_records(date_str: str):
    """
    Read graded results from DB and update /results/model_record.json
    and /results/pod_record.json.
    """
    try:
        import sqlite3
        db_path = BASE_DIR / "pipeline" / "db" / "eyeblackiq.db"
        if not db_path.exists():
            logger.warning(f"DB not found at {db_path} — skipping record update")
            return

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row

            # Overall summary
            cur = conn.execute(
                """SELECT
                       COUNT(*) as n,
                       SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) as w,
                       SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as l,
                       SUM(CASE WHEN result='PUSH' THEN 1 ELSE 0 END) as p,
                       SUM(units_net) as units
                   FROM results WHERE result IN ('WIN','LOSS','PUSH')"""
            )
            row = cur.fetchone()
            n   = row["n"] or 0
            w   = row["w"] or 0
            l   = row["l"] or 0
            p   = row["p"] or 0
            units = round(row["units"] or 0, 2)
            roi   = round((units / n * 100) if n > 0 else 0, 1)

            # Validate: w + l + p must equal n
            assert w + l + p == n, f"Record math error: {w}+{l}+{p}={w+l+p} != {n}"

            # By sport
            cur2 = conn.execute(
                """SELECT sport,
                       SUM(CASE WHEN result='WIN'  THEN 1 ELSE 0 END) as w,
                       SUM(CASE WHEN result='LOSS' THEN 1 ELSE 0 END) as l,
                       SUM(CASE WHEN result='PUSH' THEN 1 ELSE 0 END) as p,
                       SUM(units_net) as units
                   FROM results WHERE result IN ('WIN','LOSS','PUSH')
                   GROUP BY sport"""
            )
            by_sport = {}
            for r in cur2.fetchall():
                by_sport[r["sport"]] = {"w": r["w"], "l": r["l"], "p": r["p"],
                                         "units": round(r["units"] or 0, 2)}

            # Recent history
            cur3 = conn.execute(
                """SELECT r.signal_date, r.sport, r.side, s.tier, r.units, r.result, r.units_net, s.ev
                   FROM results r LEFT JOIN signals s ON s.id=r.signal_id
                   WHERE r.result IN ('WIN','LOSS','PUSH')
                   ORDER BY r.signal_date DESC, r.id DESC LIMIT 50"""
            )
            history = []
            for r in cur3.fetchall():
                history.append({
                    "date": r["signal_date"], "pick": r["side"],
                    "sport": r["sport"], "tier": r["tier"],
                    "units": r["units"], "status": r["result"],
                    "result_value": round(r["units_net"] or 0, 2),
                    "ev_pct": r["ev"],
                })

        model_record_path = BASE_DIR / "results" / "model_record.json"
        existing = {}
        if model_record_path.exists():
            with open(model_record_path) as f:
                existing = json.load(f)

        # Preserve by_tier, by_ev_bucket from existing if not rebuilt here
        model_record = {
            "last_updated": datetime.utcnow().isoformat() + "+00:00",
            "summary": {"w": w, "l": l, "p": p, "units": units, "roi_pct": roi},
            "by_sport": by_sport,
            "by_tier":  existing.get("by_tier", {}),
            "by_ev_bucket": existing.get("by_ev_bucket", {"2-4%": {}, "4-7%": {}, "7-12%": {}, "12%+": {}}),
            "history": history,
        }
        with open(model_record_path, "w") as f:
            json.dump(model_record, f, indent=2, default=str)
        logger.info(f"Updated model_record.json: {w}W-{l}L-{p}P  {units:+.2f}u  ROI={roi}%")

    except AssertionError as e:
        logger.error(f"Schema validation failed: {e}")
    except Exception as e:
        logger.error(f"Record update failed: {e}")


def main():
    parser = argparse.ArgumentParser(description="EyeBlackIQ evening runner")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date_str = args.date
    dry_run  = args.dry_run

    logger.info(f"{'='*60}")
    logger.info(f"  EyeBlackIQ Evening Run — {date_str}")
    logger.info(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"{'='*60}")

    # 1. Fetch results (scrapers)
    for scraper in ["ncaa_baseball", "mlb", "nhl", "soccer"]:
        run_cmd(f"Fetch results: {scraper}",
                [sys.executable, f"scrapers/scraper_{scraper}.py", "--date", date_str, "--mode", "results"])

    # 2. Update records from DB
    update_results_records(date_str)

    # 3. Re-export JSON
    run_cmd("Export JSON", [sys.executable, "pipeline/export.py", "--date", date_str])

    # 4. Market analyzer (update graded column)
    run_cmd("Market Analyzer", [sys.executable, "pipeline/market_analyzer.py", "--date", date_str])

    # 5. Git push (if not dry run)
    if not dry_run:
        run_cmd("Git add",    ["git", "add", "docs/", "results/"])
        run_cmd("Git commit", ["git", "commit", "-m", f"EyeBlackIQ results {date_str}"])
        run_cmd("Git push",   ["git", "push", "origin", "main"])
    else:
        logger.info("  [DRY-RUN] Skipped git push")

    logger.info(f"  Evening run complete — {date_str}")


if __name__ == "__main__":
    main()
