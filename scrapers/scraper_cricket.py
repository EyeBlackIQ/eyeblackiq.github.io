"""
EyeBlackIQ — scraper_cricket.py
Cricket schedule stub — GATE FAILED (no reliable free historical odds source found).

Usage:
  python scrapers/scraper_cricket.py --date 2026-03-21 --mode schedule

This scraper is a stub. The cricket backtesting gate was NOT passed because no free
historical odds source with reliability >= 6 was found. See docs/sport_gaps.md.

Output: JSON to stdout (always returns gate-failed notice)
"""
import sys
import json
import argparse
from datetime import datetime


def schedule(date_str: str) -> list:
    """STUB — Cricket gate failed. Returns gate status notice."""
    return [{
        "status":    "GATE_FAILED",
        "sport":     "CRICKET",
        "date":      date_str,
        "reason":    "No reliable free cricket historical odds source found (score >= 6 required). See docs/sport_gaps.md.",
        "endpoints_tested": [
            "https://site.api.espn.com/apis/site/v2/sports/cricket/wi.1/scoreboard — returned 0 events",
            "https://hs-consumer-api.espncricinfo.com/v1/pages/matches/current — connection failed",
        ],
        "recommended_path": "OddsPortal forward-logging strategy + CricSheet ball-by-ball data (no odds). Backtest possible in 6+ months.",
    }]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Cricket scraper stub")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--mode",  default="schedule", choices=["schedule", "results", "props"])
    args = parser.parse_args()
    print(json.dumps(schedule(args.date), indent=2))
