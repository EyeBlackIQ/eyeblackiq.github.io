"""
EyeBlackIQ — approve_pod.py
Flip PENDING_APPROVAL -> APPROVED in picks_today.json (or docs/data/today_slip.json).
Logs all approvals to /results/pod_approvals.json.

Usage:
  python approve_pod.py --date 2026-03-21 --sport NCAA
  python approve_pod.py --date 2026-03-21 --sport MLB
  python approve_pod.py --list              # Show pending PODs
"""
import json
import argparse
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR      = Path(__file__).parent
SLIP_PATH     = BASE_DIR / "docs" / "data" / "today_slip.json"
APPROVALS_LOG = BASE_DIR / "results" / "pod_approvals.json"


def _load_json(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def list_pending_pods(slip: dict) -> list:
    """Return POD picks with status=PENDING_APPROVAL."""
    pods = slip.get("pod", [])
    return [p for p in pods if p.get("approval_status") in ("PENDING_APPROVAL", None, "PENDING")]


def approve_pod(date_str: str, sport: str) -> bool:
    """
    Flip approval_status from PENDING_APPROVAL to APPROVED for the given sport's POD.
    Logs to pod_approvals.json.
    Returns True if found and flipped.
    """
    slip = _load_json(SLIP_PATH)
    if not slip:
        logger.error(f"Slip not found at {SLIP_PATH}")
        return False

    found = False
    for pod in slip.get("pod", []):
        pod_sport = (pod.get("sport") or "").upper()
        if sport.upper() in pod_sport or pod_sport in sport.upper():
            old_status = pod.get("approval_status", "PENDING_APPROVAL")
            pod["approval_status"] = "APPROVED"
            pod["approved_at"]     = datetime.now(timezone.utc).isoformat()
            pod["approved_by"]     = "human"
            logger.info(f"Approved POD: {sport} — {pod.get('pick','?')} ({old_status} -> APPROVED)")
            found = True

    if not found:
        logger.warning(f"No POD found for sport={sport} in slip for {date_str}")
        return False

    _write_json(SLIP_PATH, slip)

    # Log to approvals
    log = _load_json(APPROVALS_LOG)
    if not isinstance(log, list):
        log = []
    log.append({
        "date":        date_str,
        "sport":       sport.upper(),
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "slip_date":   slip.get("date", ""),
    })
    _write_json(APPROVALS_LOG, log)
    logger.info(f"Approval logged to {APPROVALS_LOG}")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Approve EyeBlackIQ POD pick")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--sport", default=None, help="NCAA | MLB | NHL | SOCCER")
    parser.add_argument("--list",  action="store_true", help="List pending PODs")
    args = parser.parse_args()

    slip = _load_json(SLIP_PATH)
    if args.list or not args.sport:
        pending = list_pending_pods(slip)
        if not pending:
            print("No pending PODs found.")
        else:
            print(f"Pending PODs ({len(pending)}):")
            for p in pending:
                print(f"  [{p.get('sport','?')}]  {p.get('pick','?')}  {p.get('odds','?')}  {p.get('units','?')}u  EV={p.get('edge','?')}%")
    else:
        ok = approve_pod(args.date, args.sport)
        print("APPROVED" if ok else "FAILED — check logs")
