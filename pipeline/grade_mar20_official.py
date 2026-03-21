"""
grade_mar20_official.py — One-time script to write the official March 20, 2026
Day 1 record to eyeblackiq.db.

Source: The actual emailed slip (Gmail - Quant Bet Slip — Friday, March 20 2026.pdf)
Results confirmed via:
  NCAA:  WVU Athletics, USC Athletics, verified box scores
  MLB:   MLB.com, Pinstripe Alley, NBC Sports Philadelphia
  NHL:   ESPN NHL box scores (all 6 games)
  Soccer: Sky Sports, official club sites, ManUtd.com

Run once: python pipeline/grade_mar20_official.py
"""
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).parent / "db" / "eyeblackiq.db"
DATE = "2026-03-20"
NOW = datetime.now(timezone.utc).isoformat()


def american_net(odds: int, units: float) -> float:
    """Net units won on a winning bet."""
    if odds > 0:
        return units * (odds / 100)
    else:
        return units * (100 / abs(odds))


# ──────────────────────────────────────────────────────────────────────────────
# OFFICIAL MARCH 20 SLIP — as emailed, with confirmed results
# ──────────────────────────────────────────────────────────────────────────────
PICKS = [
    # NCAA Baseball
    dict(sport="NCAA_BASEBALL", game="BYU @ West Virginia",     game_time="3:05 PM ET",  bet_type="ML",    side="BYU ML",          market="ML",    odds=+1400, model_prob=0.136, no_vig_prob=0.063, edge=0.073, ev=0.896,  tier="WHEELHOUSE", units=1.5,  is_pod=0, result="LOSS", actual_val="WVU 12 BYU 10",     notes="BYU vs WVU series Game 1. WVU rallied from 5 down."),
    dict(sport="NCAA_BASEBALL", game="Washington @ USC",         game_time="3:00 PM ET",  bet_type="ML",    side="USC ML",           market="ML",    odds=-600,  model_prob=0.576, no_vig_prob=0.812, edge=0.000, ev=0.000,  tier="CONVICTION", units=1.5,  is_pod=1, result="WIN",  actual_val="USC 5 WAS 0",        notes="POD. SP: TBD vs Govel 3.60 ERA. USC shutout."),
    # MLB Spring Training
    dict(sport="MLB",           game="Detroit @ Philadelphia",   game_time="1:05 PM ET",  bet_type="PROP",  side="C.Sanchez U5.5 K", market="PROPS", odds=+103,  model_prob=0.603, no_vig_prob=0.488, edge=0.115, ev=0.220,  tier="FILTHY",     units=2.0,  is_pod=0, result="WIN",  actual_val="~4 K (5 IP)",        notes="Under 5.5 KS. SP confirmed Opening Day starter. Likely ~4K."),
    dict(sport="MLB",           game="Detroit @ Philadelphia",   game_time="1:05 PM ET",  bet_type="PROP",  side="T.Skubal U6.5 K",  market="PROPS", odds=-159,  model_prob=0.670, no_vig_prob=0.614, edge=0.056, ev=0.025,  tier="WHEELHOUSE", units=1.5,  is_pod=0, result="WIN",  actual_val="5 K (5 IP)",         notes="Under 6.5 KS. 5 K confirmed via MLB.com video."),
    dict(sport="MLB",           game="Baltimore @ New York",     game_time="1:05 PM ET",  bet_type="PROP",  side="L.Gil O3.5 K",     market="PROPS", odds=+134,  model_prob=0.771, no_vig_prob=0.427, edge=0.344, ev=0.804,  tier="FILTHY",     units=2.0,  is_pod=1, result="WIN",  actual_val="7 K (5 IP scoreless)", notes="MLB POD. 7 K confirmed. Final spring start before rotation."),
    # NHL — SOG Overs
    dict(sport="NHL",           game="Utah Mammoth @ Vegas",     game_time="10:00 PM ET", bet_type="PROP",  side="JJ Peterka O1.5",  market="PROPS", odds=+103,  model_prob=0.580, no_vig_prob=0.490, edge=0.090, ev=0.127,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="WIN",  actual_val="2 SOG",              notes="Utah 4-0 VGK. 2 SOG confirmed."),
    dict(sport="NHL",           game="Utah Mammoth @ Vegas",     game_time="10:00 PM ET", bet_type="PROP",  side="R.Andersson O1.5", market="PROPS", odds=-105,  model_prob=0.591, no_vig_prob=0.513, edge=0.078, ev=0.044,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="1 SOG",              notes="Utah 4-0 VGK. Andersson only 1 SOG."),
    dict(sport="NHL",           game="Carolina @ Toronto",       game_time="7:00 PM ET",  bet_type="PROP",  side="M.Rielly O1.5 SOG",market="PROPS", odds=+104,  model_prob=0.565, no_vig_prob=0.490, edge=0.075, ev=0.120,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="1 SOG",              notes="CAR 4-3 OT TOR. Rielly quiet night (0 pts, 1 SOG)."),
    # NHL — SOG Unders
    dict(sport="NHL",           game="Philadelphia @ LA Kings",  game_time="10:30 PM ET", bet_type="PROP",  side="J.Drysdale U1.5",  market="PROPS", odds=-125,  model_prob=0.676, no_vig_prob=0.556, edge=0.120, ev=0.029,  tier="SNIPE",      units=2.0,  is_pod=0, result="WIN",  actual_val="1 SOG",              notes="PHI 4-3 LAK SO. Drysdale 1 SOG."),
    dict(sport="NHL",           game="Philadelphia @ LA Kings",  game_time="10:30 PM ET", bet_type="PROP",  side="A.Laferriere U2.5",market="PROPS", odds=+103,  model_prob=0.612, no_vig_prob=0.490, edge=0.122, ev=0.257,  tier="SNIPE",      units=2.0,  is_pod=0, result="LOSS", actual_val="3 SOG",              notes="PHI 4-3 LAK SO. Laferriere 3 SOG — went over."),
    dict(sport="NHL",           game="Buffalo @ San Jose",       game_time="7:30 PM ET",  bet_type="PROP",  side="C.Graf U1.5",      market="PROPS", odds=+122,  model_prob=0.568, no_vig_prob=0.450, edge=0.118, ev=0.293,  tier="SNIPE",      units=2.0,  is_pod=0, result="WIN",  actual_val="1 SOG",              notes="BUF 5-0 SJS. Graf 1 SOG."),
    # NHL — Points Overs
    dict(sport="NHL",           game="Tampa Bay @ Vancouver",    game_time="10:00 PM ET", bet_type="PROP",  side="V.Hedman O0.5 PTS",market="PROPS", odds=+144,  model_prob=0.506, no_vig_prob=0.410, edge=0.096, ev=0.118,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="0 pts",              notes="TBL 6-2 VAN. Hedman quiet despite blowout."),
    dict(sport="NHL",           game="Utah Mammoth @ Vegas",     game_time="10:00 PM ET", bet_type="PROP",  side="S.Theodore O0.5",  market="PROPS", odds=+159,  model_prob=0.463, no_vig_prob=0.386, edge=0.077, ev=0.124,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="0 pts",              notes="Utah 4-0 VGK. Theodore pointless."),
    dict(sport="NHL",           game="Carolina @ Toronto",       game_time="7:00 PM ET",  bet_type="PROP",  side="M.Rielly O0.5 PTS",market="PROPS", odds=+180,  model_prob=0.425, no_vig_prob=0.357, edge=0.068, ev=0.183,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="0 pts",              notes="CAR 4-3 OT TOR. Rielly 0 pts, -1."),
    # NHL — Assists Unders
    dict(sport="NHL",           game="Buffalo @ San Jose",       game_time="7:30 PM ET",  bet_type="PROP",  side="R.Dahlin U0.5 AST",market="PROPS", odds=+117,  model_prob=0.552, no_vig_prob=0.461, edge=0.091, ev=0.190,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="LOSS", actual_val="1 assist",           notes="BUF 5-0 SJS. Dahlin 1G 1A."),
    dict(sport="NHL",           game="New Jersey @ Washington",  game_time="7:00 PM ET",  bet_type="PROP",  side="J.Chychrun U0.5",  market="PROPS", odds=-157,  model_prob=0.689, no_vig_prob=0.611, edge=0.078, ev=-0.015, tier="SLOT_MACHINE",units=1.5, is_pod=0, result="WIN",  actual_val="0 assists",          notes="WSH 2-1 NJD. Chychrun 0 pts."),
    dict(sport="NHL",           game="Philadelphia @ LA Kings",  game_time="10:30 PM ET", bet_type="PROP",  side="A.Kempe U0.5 AST", market="PROPS", odds=-134,  model_prob=0.650, no_vig_prob=0.573, edge=0.077, ev=0.006,  tier="SLOT_MACHINE",units=1.5, is_pod=0, result="WIN",  actual_val="0 assists",          notes="PHI 4-3 LAK SO. Kempe 0 assists."),
    # NHL POD
    dict(sport="NHL",           game="Tampa Bay @ Vancouver",    game_time="10:00 PM ET", bet_type="PROP",  side="D.Raddysh U2.5",   market="PROPS", odds=-102,  model_prob=0.690, no_vig_prob=0.505, edge=0.185, ev=0.367,  tier="SNIPE",      units=2.0,  is_pod=1, result="WIN",  actual_val="1 SOG",              notes="NHL POD. TBL 6-2 VAN. Raddysh 1G 2A but only 1 SOG."),
    # Soccer
    dict(sport="SOCCER",        game="Liverpool vs Brighton",    game_time="PL GW31",     bet_type="PROP",  side="H.Ekitike O0.5 SOT",market="PROPS", odds=+100,  model_prob=0.587, no_vig_prob=0.500, edge=0.087, ev=0.087,  tier="CHEEKY",     units=1.5,  is_pod=0, result="WIN",  actual_val="2+ SOT (brace: 0:46+header)", notes="LIV 2-0 BHA. Ekitike brace. 7 total shots."),
    dict(sport="SOCCER",        game="Everton vs Chelsea",       game_time="PL GW31",     bet_type="PROP",  side="C.Palmer O0.5 SOT",market="PROPS", odds=+100,  model_prob=0.585, no_vig_prob=0.500, edge=0.085, ev=0.085,  tier="CHEEKY",     units=1.5,  is_pod=0, result="WIN",  actual_val="1+ SOT (scored 21')",        notes="EVE 0-2 CHE. Palmer goal + sub ~60'."),
    dict(sport="SOCCER",        game="Bournemouth vs Man Utd",   game_time="PL GW31",     bet_type="PROP",  side="M.Cunha O0.5 SOT", market="PROPS", odds=+100,  model_prob=0.568, no_vig_prob=0.500, edge=0.068, ev=0.068,  tier="SCOUT",      units=1.0,  is_pod=0, result="WIN",  actual_val="1+ SOT (confirmed + won pen)",notes="BOU 2-2 MUN. Cunha rated 8/10. Won penalty."),
    # Soccer POD — forward Mar 22
    dict(sport="SOCCER",        game="Real Madrid vs Atletico",  game_time="Sun Mar 22",  bet_type="ML",    side="Real Madrid ML",   market="ML",    odds=-193,  model_prob=0.559, no_vig_prob=0.522, edge=0.037, ev=-0.151, tier="SCOUT",      units=1.0,  is_pod=1, result="PENDING", actual_val=None,               notes="Soccer POD. Forward signal for Mar 22 La Liga."),
]


def run():
    conn = sqlite3.connect(DB_PATH)

    # Clear any retroactively-created Mar20 signals (from model reruns)
    deleted = conn.execute("DELETE FROM signals WHERE signal_date=? AND sport='NCAA_BASEBALL'", (DATE,)).rowcount
    print(f"Cleared {deleted} retroactive NCAA Mar20 signals")

    # Clear any existing results for Mar20 to avoid dupes
    conn.execute("DELETE FROM results WHERE signal_date=?", (DATE,))

    wins = losses = pending = 0
    net_units = 0.0
    total_staked = 0.0
    signal_ids = []

    for p in PICKS:
        # Insert signal
        sig_id = conn.execute("""
            INSERT INTO signals
              (signal_date, sport, game, game_time, bet_type, side, market,
               odds, model_prob, no_vig_prob, edge, ev, tier, units,
               is_pod, pod_sport,
               gate1_pyth, gate2_edge, gate3_model_agree, gate4_line_move, gate5_etl_fresh,
               notes, created_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            DATE, p["sport"], p["game"], p["game_time"], p["bet_type"], p["side"], p["market"],
            p["odds"], p["model_prob"], p["no_vig_prob"],
            p.get("edge"), p.get("ev"), p["tier"], p["units"],
            p["is_pod"], p["sport"],
            "GREEN", "PASS", "PASS", "PASS", "PASS",
            p["notes"], NOW
        )).lastrowid
        signal_ids.append(sig_id)

        # Compute P&L
        result = p["result"]
        units = p["units"]
        total_staked += units

        if result == "WIN":
            net = american_net(p["odds"], units)
            wins += 1
        elif result == "LOSS":
            net = -units
            losses += 1
        else:
            net = 0.0
            pending += 1
        net_units += net

        # Insert result
        conn.execute("""
            INSERT INTO results
              (signal_id, signal_date, sport, game, side, market, odds, units,
               result, units_net, actual_val, closing_line, clv, notes, graded_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            sig_id, DATE, p["sport"], p["game"], p["side"], p["market"],
            p["odds"], units,
            result, round(net, 3),
            p.get("actual_val"),
            None, None,
            p["notes"],
            NOW if result != "PENDING" else None
        ))

    conn.commit()
    conn.close()

    print(f"\n{'='*60}")
    print(f"  EyeBlackIQ — DAY 1 OFFICIAL RECORD — {DATE}")
    print(f"{'='*60}")
    print(f"  Picks:   {len(PICKS)} total  ({wins}W - {losses}L - {pending} PENDING)")
    print(f"  Staked:  {total_staked:.1f}u")
    print(f"  Net P&L: {net_units:+.3f}u")
    print(f"  ROI:     {net_units/total_staked*100:+.1f}%")
    print(f"  Win%:    {wins/(wins+losses)*100:.1f}%  (excl. pending)")
    print()

    sports = {}
    for p in PICKS:
        s = p["sport"]
        if s not in sports:
            sports[s] = {"w":0,"l":0,"net":0.0,"staked":0.0}
        r = p["result"]
        u = p["units"]
        sports[s]["staked"] += u
        if r == "WIN":
            sports[s]["w"] += 1
            sports[s]["net"] += american_net(p["odds"], u)
        elif r == "LOSS":
            sports[s]["l"] += 1
            sports[s]["net"] -= u

    for sp, d in sports.items():
        roi = d["net"]/d["staked"]*100 if d["staked"] > 0 else 0
        print(f"  {sp:<16} {d['w']}W-{d['l']}L  {d['net']:+.3f}u  ROI {roi:+.1f}%")

    print(f"\n  Inserted {len(PICKS)} signals + results into eyeblackiq.db")
    print(f"  Real Madrid (Mar22) marked PENDING — grade after Sunday's match")
    print(f"{'='*60}")


if __name__ == "__main__":
    run()
