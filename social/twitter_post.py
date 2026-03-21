"""
EyeBlackIQ — twitter_post.py
Format and post daily picks + results to X (Twitter).

Usage:
  python social/twitter_post.py --date 2026-03-21 --mode daily_picks
  python social/twitter_post.py --date 2026-03-21 --mode results
  python social/twitter_post.py --test          (print without posting)
  python social/twitter_post.py --test --mode daily_picks

Requires in .env:
  TWITTER_API_KEY, TWITTER_API_SECRET,
  TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET,
  TWITTER_BEARER_TOKEN, TWITTER_ENABLED, SITE_URL
"""
import os
import sys
import json
import argparse
import logging
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)-7s %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR     = Path(__file__).parent.parent
SLIP_PATH    = BASE_DIR / "docs" / "data" / "today_slip.json"
RECORD_PATH  = BASE_DIR / "docs" / "data" / "record.json"
RESULTS_PATH = BASE_DIR / "docs" / "data" / "results.json"

SITE_URL         = os.getenv("SITE_URL", "https://eyeblackiq.github.io")
TWITTER_ENABLED  = os.getenv("TWITTER_ENABLED", "false").lower() == "true"
MAX_TWEET_LEN    = 280
THREAD_THRESHOLD = 10   # >10 picks: post as thread by sport


def _load(path: Path) -> dict:
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _tier_emoji(tier: str) -> str:
    t = (tier or "").upper()
    if any(k in t for k in ["FILTHY", "SNIPE", "UPPER 90", "SCREAMER"]): return "🔴"
    if any(k in t for k in ["WHEELHOUSE", "SLOT MACHINE", "CHEEKY", "FAST BREAK"]): return "🔵"
    if "SCOUT" in t: return "🟡"
    return "⚫"


def _sport_emoji(sport: str) -> str:
    return {"NCAA": "⚾", "MLB": "⚾", "NHL": "🏒", "SOCCER": "⚽"}.get((sport or "").upper(), "📊")


def _odds_str(odds) -> str:
    if odds is None: return "—"
    odds = int(odds)
    return f"+{odds}" if odds > 0 else str(odds)


def _pick_line(pick: dict) -> str:
    """Format a single pick for a tweet line."""
    sport  = _sport_emoji(pick.get("sport", ""))
    tier   = _tier_emoji(pick.get("tier", ""))
    side   = pick.get("side") or pick.get("pick") or "—"
    odds   = _odds_str(pick.get("odds"))
    units  = pick.get("units", 1.0)
    # edge field is already in percentage scale (e.g. 10.62 means 10.62%)
    edge   = pick.get("edge_pct") or pick.get("edge") or 0
    pod    = " 📌 POD" if pick.get("is_pod") else ""
    return f"{sport}{tier} {side} ({odds}) {units}u | Edge +{edge:.1f}%{pod}"


def format_daily_picks(date_str: str) -> list:
    """
    Format daily picks as tweet text(s).
    Returns list of tweet strings (1 or more for thread).
    """
    slip = _load(SLIP_PATH)
    rec  = _load(RECORD_PATH)

    picks = slip.get("recommended", [])
    pods  = slip.get("pod", [])

    if not picks and not pods:
        return [f"No plays today meeting edge threshold. Watching the market.\n\n{SITE_URL}"]

    # Format date nicely
    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_label = d.strftime("%a %b %-d")
    except Exception:
        date_label = date_str

    # Record summary line
    w   = rec.get("wins", 0)
    l   = rec.get("losses", 0)
    net = rec.get("net_units", 0.0)
    roi = rec.get("roi", 0.0)
    rec_line = f"Season: {w}W-{l}L  {'+' if net>=0 else ''}{net:.1f}u  ROI {'+' if roi>=0 else ''}{roi:.1f}%"

    if len(picks) <= THREAD_THRESHOLD:
        # Single tweet
        lines = [f"EyeBlackIQ | {date_label}", ""]
        if pods:
            for pod in pods:
                lines.append(f"📌 POD: {_pick_line(pod)}")
            lines.append("")
        for p in picks:
            if not p.get("is_pod"):
                lines.append(_pick_line(p))
        lines.extend(["", rec_line, "", SITE_URL])
        tweet = "\n".join(lines)
        # Truncate if over limit
        if len(tweet) > MAX_TWEET_LEN:
            tweet = tweet[:MAX_TWEET_LEN - 30] + f"...\n\n{SITE_URL}"
        return [tweet]
    else:
        # Thread by sport
        tweets = []
        header = f"EyeBlackIQ | {date_label} — {len(picks)} plays across {len(set(p.get('sport','?') for p in picks))} sports\n\n{rec_line}\n\n{SITE_URL}"
        tweets.append(header)
        by_sport = {}
        for p in picks:
            sport = (p.get("sport") or "OTHER").upper()
            by_sport.setdefault(sport, []).append(p)
        for sport, sport_picks in sorted(by_sport.items()):
            emoji = _sport_emoji(sport)
            lines = [f"{emoji} {sport} ({len(sport_picks)} plays)", ""]
            for p in sport_picks:
                lines.append(_pick_line(p))
            tweet = "\n".join(lines)
            if len(tweet) > MAX_TWEET_LEN:
                tweet = tweet[:MAX_TWEET_LEN - 6] + "..."
            tweets.append(tweet)
        return tweets


def format_results(date_str: str) -> list:
    """Format results tweet for a date."""
    results_data = _load(RESULTS_PATH)
    rec          = _load(RECORD_PATH)
    picks        = results_data.get("picks", [])

    # Filter to target date
    day_picks = [p for p in picks if (p.get("date") or p.get("signal_date", "")) == date_str]

    if not day_picks:
        return [f"No graded results found for {date_str}. Pending official scores."]

    try:
        d = datetime.strptime(date_str, "%Y-%m-%d")
        date_label = d.strftime("%a %b %-d")
    except Exception:
        date_label = date_str

    wins  = sum(1 for p in day_picks if (p.get("result","") or "").upper().startswith("W"))
    losses = sum(1 for p in day_picks if (p.get("result","") or "").upper().startswith("L"))
    pushes = sum(1 for p in day_picks if (p.get("result","") or "").upper().startswith("P"))
    net   = sum(p.get("units_net") or p.get("net_units") or 0 for p in day_picks)

    lines = [
        f"EyeBlackIQ Results | {date_label}",
        f"{wins}W-{losses}L-{pushes}P  {'+' if net>=0 else ''}{net:.2f}u",
        "",
    ]
    for p in day_picks[:6]:  # cap at 6 for tweet length
        result_sym = "✓" if (p.get("result","") or "").upper().startswith("W") else ("✗" if (p.get("result","") or "").upper().startswith("L") else "→")
        sport   = _sport_emoji(p.get("sport",""))
        side    = p.get("side") or p.get("pick") or "—"
        net_p   = p.get("units_net") or p.get("net_units") or 0
        lines.append(f"{result_sym} {sport} {side}  {'+' if net_p>=0 else ''}{net_p:.2f}u")

    # Season summary
    w   = rec.get("wins", 0)
    l   = rec.get("losses", 0)
    roi = rec.get("roi", 0.0)
    lines.extend(["", f"Season: {w}W-{l}L  ROI {'+' if roi>=0 else ''}{roi:.1f}%", "", SITE_URL])

    tweet = "\n".join(lines)
    if len(tweet) > MAX_TWEET_LEN:
        tweet = tweet[:MAX_TWEET_LEN - 30] + f"...\n\n{SITE_URL}"
    return [tweet]


def post_tweets(tweets: list, test_mode: bool = False):
    """Post a list of tweet strings. First is root, rest are thread replies."""
    if test_mode:
        sep = "=" * 60
        sys.stdout.buffer.write(f"{sep}\nTEST MODE — would post:\n".encode("utf-8"))
        for i, t in enumerate(tweets):
            sys.stdout.buffer.write(f"\n--- Tweet {i+1} ({len(t)} chars) ---\n{t}\n".encode("utf-8"))
        sys.stdout.buffer.write(f"{sep}\n".encode("utf-8"))
        sys.stdout.buffer.flush()
        return

    if not TWITTER_ENABLED:
        logger.info("TWITTER_ENABLED=false — skipping post")
        return

    try:
        import tweepy
    except ImportError:
        logger.error("tweepy not installed. Run: pip install tweepy")
        return

    api_key    = os.getenv("TWITTER_API_KEY")
    api_secret = os.getenv("TWITTER_API_SECRET")
    token      = os.getenv("TWITTER_ACCESS_TOKEN")
    token_sec  = os.getenv("TWITTER_ACCESS_TOKEN_SECRET")

    if not all([api_key, api_secret, token, token_sec]):
        logger.error("Twitter credentials missing from .env — cannot post")
        return

    client = tweepy.Client(
        consumer_key=api_key, consumer_secret=api_secret,
        access_token=token, access_token_secret=token_sec
    )

    reply_to_id = None
    for i, tweet_text in enumerate(tweets):
        try:
            if reply_to_id:
                resp = client.create_tweet(text=tweet_text, in_reply_to_tweet_id=reply_to_id)
            else:
                resp = client.create_tweet(text=tweet_text)
            reply_to_id = resp.data["id"]
            logger.info(f"Posted tweet {i+1}/{len(tweets)}: id={reply_to_id}")
        except Exception as e:
            logger.error(f"Failed to post tweet {i+1}: {e}")
            break


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EyeBlackIQ Twitter post formatter")
    parser.add_argument("--date",  default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--mode",  default="daily_picks", choices=["daily_picks", "results"])
    parser.add_argument("--test",  action="store_true", help="Print without posting")
    args = parser.parse_args()

    if args.mode == "daily_picks":
        tweets = format_daily_picks(args.date)
    else:
        tweets = format_results(args.date)

    post_tweets(tweets, test_mode=args.test or not TWITTER_ENABLED)
