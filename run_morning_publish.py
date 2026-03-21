"""
EyeBlackIQ — run_morning_publish.py
Rebuild website -> git commit+push -> post Twitter (if enabled).

Usage:
  python run_morning_publish.py                      # Today
  python run_morning_publish.py --date 2026-03-21
  python run_morning_publish.py --date 2026-03-21 --dry-run

--dry-run: Skip git push and Twitter post.
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

BASE_DIR        = Path(__file__).parent
TWITTER_ENABLED = os.getenv("TWITTER_ENABLED", "false").lower() == "true"


def run_cmd(label: str, cmd: list, cwd=None) -> bool:
    logger.info(f"  >>> {label}")
    try:
        r = subprocess.run(cmd, capture_output=False, text=True, cwd=cwd or BASE_DIR)
        return r.returncode == 0
    except Exception as e:
        logger.error(f"  ERROR: {label} — {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="EyeBlackIQ morning publish")
    parser.add_argument("--date",    default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date_str = args.date
    dry_run  = args.dry_run

    logger.info(f"  EyeBlackIQ Publish — {date_str}  ({'DRY RUN' if dry_run else 'LIVE'})")

    # 1. Re-export JSON (idempotent)
    run_cmd("Export JSON", [sys.executable, "pipeline/export.py", "--date", date_str])

    # 2. Git add + commit
    if not dry_run:
        run_cmd("Git add", ["git", "add", "docs/"])
        msg = f"EyeBlackIQ picks {date_str}"
        run_cmd("Git commit", ["git", "commit", "-m", msg])
        run_cmd("Git push",   ["git", "push", "origin", "main"])
    else:
        logger.info("  [DRY-RUN] Skipped git push")

    # 3. Twitter post
    if TWITTER_ENABLED and not dry_run:
        run_cmd("Twitter post",
                [sys.executable, "social/twitter_post.py", "--date", date_str, "--mode", "daily_picks"])
    elif not TWITTER_ENABLED:
        logger.info("  Twitter disabled (TWITTER_ENABLED=false in .env)")
    else:
        logger.info("  [DRY-RUN] Skipped Twitter post")

    logger.info(f"  Publish complete — {date_str}")


if __name__ == "__main__":
    main()
