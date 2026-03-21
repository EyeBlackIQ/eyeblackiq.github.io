"""
EyeBlackIQ — scraper_handball.py
Handball schedule stub — GATE FAILED (no reliable free historical odds source found).

Usage:
  python scrapers/scraper_handball.py --date 2026-03-21 --mode schedule

This scraper is a stub. The handball backtesting gate was NOT passed. See docs/sport_gaps.md.

Output: JSON to stdout (always returns gate-failed notice)
"""
import sys
import json
import argparse
from datetime import datetime


def schedule(date_str: str) -> list:
    """STUB — Handball gate failed. Returns gate status notice."""
    return [{
        "status":    "GATE_FAILED",
        "sport":     "HANDBALL",
        "date":      date_str,
        "reason":    "No free handball API with historical odds. EHF requires commercial license. ESPN has no handball endpoint.",
        "endpoints_tested": [
            "https://competitionmanager.ehf.eu/api/matches — requires paid commercial license",
            "https://site.api.espn.com/apis/site/v2/sports/handball/all.handball/scoreboard — endpoint does not exist",
        ],
        "recommended_path": "OddsPortal forward-logging strategy starting now. Backtest possible in 6+ months with 500+ graded matches.",
    }]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Handball scraper stub")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--mode",  default="schedule", choices=["schedule", "results", "props"])
    args = parser.parse_args()
    print(json.dumps(schedule(args.date), indent=2))
