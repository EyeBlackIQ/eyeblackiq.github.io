"""
EyeBlackIQ — run_morning.py
Daily morning runner: fetch schedules -> run model -> select PODs -> market analyzer.

Usage:
  python run_morning.py                      # Today
  python run_morning.py --date 2026-03-21
  python run_morning.py --date 2026-03-21 --dry-run

--dry-run: Skips git push and Twitter post. Safe for testing.
"""
import argparse
import logging
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


def run_step(label: str, cmd: list, dry_run: bool = False, skip_on_dry: bool = False):
    """Run a subprocess step with logging."""
    if skip_on_dry and dry_run:
        logger.info(f"  [DRY-RUN skip] {label}")
        return True
    logger.info(f"  >>> {label}")
    try:
        result = subprocess.run(cmd, capture_output=False, text=True, cwd=BASE_DIR)
        if result.returncode != 0:
            logger.error(f"  FAILED: {label} (exit {result.returncode})")
            return False
        return True
    except Exception as e:
        logger.error(f"  ERROR: {label} — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="EyeBlackIQ morning runner")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true", help="Skip git push and Twitter")
    args = parser.parse_args()

    date_str = args.date
    dry_run  = args.dry_run

    logger.info(f"{'='*60}")
    logger.info(f"  EyeBlackIQ Morning Run — {date_str}")
    logger.info(f"  Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    logger.info(f"{'='*60}")

    steps = [
        ("Fetch Lines (TheRundown)", [sys.executable, "scrapers/fetch_lines.py", "--date", date_str, "--sport", "all"], False),
        ("NCAA Baseball Signals",    [sys.executable, "pods/ncaa_baseball/model.py", "--date", date_str], False),
        ("MLB Signals",              [sys.executable, "pods/mlb/model.py", "--date", date_str], False),
        ("NHL Signals",              [sys.executable, "pods/nhl/model.py", "--date", date_str], False),
        ("Soccer Signals",           [sys.executable, "pods/soccer/model.py", "--date", date_str], False),
        ("Market Analyzer",          [sys.executable, "pipeline/market_analyzer.py", "--date", date_str], False),
        ("Export JSON",              [sys.executable, "pipeline/export.py", "--date", date_str], False),
    ]

    failures = 0
    for label, cmd, skip in steps:
        ok = run_step(label, cmd, dry_run, skip_on_dry=skip)
        if not ok:
            failures += 1
            logger.warning(f"  Step '{label}' failed — continuing")

    logger.info(f"\n{'='*60}")
    if failures == 0:
        logger.info(f"  Morning run COMPLETE — {date_str}  (0 failures)")
    else:
        logger.warning(f"  Morning run DONE with {failures} failures — {date_str}")
    logger.info(f"{'='*60}")

    # Print POD candidates from today_slip.json
    slip_path = BASE_DIR / "docs" / "data" / "today_slip.json"
    if slip_path.exists():
        import json
        with open(slip_path) as f:
            slip = json.load(f)
        pods = slip.get("pod", [])
        recs = slip.get("recommended", [])
        logger.info(f"\n  Today's Slip: {len(recs)} picks | {len(pods)} POD(s)")
        if pods:
            logger.info("  POD candidates:")
            for p in pods:
                logger.info(f"    [{p.get('sport','?')}] {p.get('pick','?')}  {p.get('odds','?')}  {p.get('units','?')}u  EV={p.get('edge','?')}%")
        else:
            logger.info("  No PODs today (requires HIGH confidence + WHEELHOUSE tier)")


if __name__ == "__main__":
    main()
