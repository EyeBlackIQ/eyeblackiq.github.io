"""
Grade the March 20, 2026 bet slip — writes results to /results/
Run: python pipeline/grade_mar20.py
"""
import json, os
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RESULTS = os.path.join(ROOT, "results")
os.makedirs(RESULTS, exist_ok=True)

# ── ALL OFFICIAL PICKS ────────────────────────────────────────────────────────
picks = [
    # NCAA Baseball
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"BYU",
     "market":"BYU ML","line":"+1400","direction":"ML_AWAY","units":1.5,
     "tier":"WHEELHOUSE","ev_pct":None,"is_pod":False,"pod_sport":None,
     "status":"LOSS","actual_val":None,"result_value":-1.5,"result_source":"ESPN",
     "notes":"WVU won 12-10. BYU LEAN label."},

    # NCAA POD
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"USC",
     "market":"USC ML","line":"-600","direction":"ML_HOME","units":1.5,
     "tier":"WHEELHOUSE","ev_pct":None,"is_pod":True,"pod_sport":"NCAA_POD",
     "status":"WIN","actual_val":None,"result_value":0.25,"result_source":"ESPN",
     "notes":"USC won 5-0. CONVICTION PLAY. POD."},

    # MLB Props
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Cristopher Sanchez",
     "market":"u5.5 Strikeouts","line":"5.5","direction":"UNDER","units":2.0,
     "tier":"FILTHY","ev_pct":14.4,"is_pod":False,"pod_sport":None,
     "status":"WIN","actual_val":4,"result_value":2.06,"result_source":"MLB_STATSAPI",
     "notes":"Sanchez K=4, IP=5.0. DET@PHI Spring Training."},

    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Tarik Skubal",
     "market":"u6.5 Strikeouts","line":"6.5","direction":"UNDER","units":1.5,
     "tier":"WHEELHOUSE","ev_pct":9.8,"is_pod":False,"pod_sport":None,
     "status":"WIN","actual_val":5,"result_value":0.94,"result_source":"MLB_STATSAPI",
     "notes":"Skubal K=5, IP=4.0. DET@PHI Spring Training."},

    # MLB POD — REINSTATED (was in flagged section only, not K_OVERS list)
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Luis Gil",
     "market":"o3.5 Strikeouts","line":"3.5","direction":"OVER","units":2.0,
     "tier":"FILTHY","ev_pct":37.2,"is_pod":True,"pod_sport":"MLB_POD",
     "status":"WIN","actual_val":7,"result_value":2.68,"result_source":"MLB_STATSAPI",
     "notes":"REINSTATED: MLB_POD for 2026-03-20. Excluded from slip body in error (Bug #001). Gil K=7, IP=5.0. BAL@NYY Spring Training."},

    # NHL CAR@TOR (confirmed game — id=2025021094)
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Morgan Rielly",
     "market":"o1.5 Shots on Goal","line":"1.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":9.8,"is_pod":False,"pod_sport":None,
     "status":"LOSS","actual_val":1,"result_value":-1.5,"result_source":"NHL_API",
     "notes":"CAR@TOR. Rielly SOG=1 (needed >1.5)."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Morgan Rielly",
     "market":"o0.5 Points","line":"0.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":8.6,"is_pod":False,"pod_sport":None,
     "status":"LOSS","actual_val":0,"result_value":-1.5,"result_source":"NHL_API",
     "notes":"CAR@TOR. Rielly PTS=0."},

    # NHL NJD@WSH (confirmed game — id=2025021095)
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Jakob Chychrun",
     "market":"u0.5 Assists","line":"0.5","direction":"UNDER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":10.8,"is_pod":False,"pod_sport":None,
     "status":"WIN","actual_val":0,"result_value":0.95,"result_source":"NHL_API",
     "notes":"NJD@WSH. Chychrun AST=0."},

    # NHL — games not found in NHL API for 2026-03-20 (schedule mismatch) → PENDING
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"JJ Peterka",
     "market":"o1.5 Shots on Goal","line":"1.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":11.0,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed UTA@VGK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Rasmus Andersson",
     "market":"o1.5 Shots on Goal","line":"1.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":10.4,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed UTA@VGK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Jamie Drysdale",
     "market":"u1.5 Shots on Goal","line":"1.5","direction":"UNDER","units":2.0,
     "tier":"SNIPE","ev_pct":14.6,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed PHI@LAK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Alex Laferriere",
     "market":"u2.5 Shots on Goal","line":"2.5","direction":"UNDER","units":2.0,
     "tier":"SNIPE","ev_pct":14.3,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed PHI@LAK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Collin Graf",
     "market":"u1.5 Shots on Goal","line":"1.5","direction":"UNDER","units":2.0,
     "tier":"SNIPE","ev_pct":14.0,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed BUF@SJS — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Victor Hedman",
     "market":"o0.5 Points","line":"0.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":11.6,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed TBL@VAN — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Shea Theodore",
     "market":"o0.5 Points","line":"0.5","direction":"OVER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":9.5,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed UTA@VGK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Rasmus Dahlin",
     "market":"u0.5 Assists","line":"0.5","direction":"UNDER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":11.3,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed BUF@SJS — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Adrian Kempe",
     "market":"u0.5 Assists","line":"0.5","direction":"UNDER","units":1.5,
     "tier":"SLOT_MACHINE","ev_pct":10.5,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Listed PHI@LAK — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    # NHL POD (Darren Raddysh) — game not found
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Darren Raddysh",
     "market":"u2.5 Shots on Goal","line":"2.5","direction":"UNDER","units":2.0,
     "tier":"SNIPE","ev_pct":21.1,"is_pod":True,"pod_sport":"NHL_POD",
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"NHL POD. Listed TBL@VAN — game not found in NHL API for 2026-03-20. Schedule mismatch."},

    # Soccer
    {"date":"2026-03-20","sport":"SOCCER","market_type":"ML","player_or_team":"Real Madrid",
     "market":"Real Madrid ML","line":"-193","direction":"ML_HOME","units":1.0,
     "tier":"MONITOR","ev_pct":3.7,"is_pod":True,"pod_sport":"SOCCER_POD",
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"SOCCER POD. Real Madrid vs Atletico Madrid, Sun Mar 22. Forward pick."},

    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Hugo Ekitike",
     "market":"o0.5 Shots on Target","line":"0.5","direction":"OVER","units":1.5,
     "tier":"CHEEKY","ev_pct":6.6,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Liverpool vs Brighton — EPL 2026-03-21. Not yet played."},

    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Cole Palmer",
     "market":"o0.5 Shots on Target","line":"0.5","direction":"OVER","units":1.5,
     "tier":"CHEEKY","ev_pct":6.3,"is_pod":False,"pod_sport":None,
     "status":"PENDING","actual_val":None,"result_value":None,"result_source":None,
     "notes":"Chelsea vs Everton — EPL 2026-03-21. Not yet played."},

    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Matheus Cunha",
     "market":"o0.5 Shots on Target","line":"0.5","direction":"OVER","units":1.0,
     "tier":"MONITOR","ev_pct":4.7,"is_pod":False,"pod_sport":None,
     "status":"WIN","actual_val":1,"result_value":1.0,"result_source":"ESPN_SOCCER",
     "notes":"MU vs Bournemouth 2-2. Cunha SOT=1."},
]

# ── FLAGGED PICKS (not recommended) ─────────────────────────────────────────
flagged = [
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Oregon",
     "market":"Oregon ML","line":"-470","direction":"ML_HOME","units":0,"tier":"FLAGGED",
     "ev_pct":0.1,"is_pod":False,"pod_sport":None,"status":"WIN","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge <3%. Oregon won 20-6. Not a pick."},
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Minnesota",
     "market":"Minnesota ML","line":"-125","direction":"ML_AWAY","units":0,"tier":"FLAGGED",
     "ev_pct":2.4,"is_pod":False,"pod_sport":None,"status":"LOSS","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge <3%. Indiana won 8-6. Not a pick."},
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Washington",
     "market":"Washington ML","line":"+400","direction":"ML_AWAY","units":0,"tier":"FLAGGED",
     "ev_pct":23.7,"is_pod":False,"pod_sport":None,"status":"LOSS","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge >15% artifact. USC won 5-0. Not a pick."},
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Oklahoma",
     "market":"Oklahoma ML","line":"+110","direction":"ML_AWAY","units":0,"tier":"FLAGGED",
     "ev_pct":22.7,"is_pod":False,"pod_sport":None,"status":"WIN","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge >15% artifact. OU won 4-2. Not a pick."},
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Florida",
     "market":"Florida ML","line":"-185","direction":"ML_AWAY","units":0,"tier":"FLAGGED",
     "ev_pct":2.3,"is_pod":False,"pod_sport":None,"status":"LOSS","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge <3%. Alabama won 6-0. Not a pick."},
    {"date":"2026-03-20","sport":"NCAA","market_type":"ML","player_or_team":"Texas",
     "market":"Texas ML","line":"-135","direction":"ML_AWAY","units":0,"tier":"FLAGGED",
     "ev_pct":0.8,"is_pod":False,"pod_sport":None,"status":"LOSS","actual_val":None,
     "result_value":0,"result_source":"ESPN","notes":"FLAGGED edge <3%. Auburn won 4-3. Not a pick."},
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Luis Gil (FLAGGED body)",
     "market":"o3.5 Strikeouts","line":"3.5","direction":"OVER","units":0,"tier":"FLAGGED",
     "ev_pct":37.2,"is_pod":False,"pod_sport":None,"status":"WIN","actual_val":7,
     "result_value":0,"result_source":"MLB_STATSAPI","notes":"FLAGGED in slip body (edge >15%) — but is MLB POD (reinstated above). K=7."},
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Andre Pallante",
     "market":"o3.5 Strikeouts","line":"3.5","direction":"OVER","units":0,"tier":"FLAGGED",
     "ev_pct":24.1,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. STL@NYM Spring Training. Not graded."},
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Eury Perez",
     "market":"o4.5 Strikeouts","line":"4.5","direction":"OVER","units":0,"tier":"FLAGGED",
     "ev_pct":20.2,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. MIA@HOU Spring Training. Not graded."},
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Max Scherzer",
     "market":"o4.5 Strikeouts","line":"4.5","direction":"OVER","units":0,"tier":"FLAGGED",
     "ev_pct":19.9,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. TOR@MIN Spring Training. Not graded."},
    {"date":"2026-03-20","sport":"MLB","market_type":"PLAYER_PROP","player_or_team":"Jose Soriano",
     "market":"o4.5 Strikeouts","line":"4.5","direction":"OVER","units":0,"tier":"FLAGGED",
     "ev_pct":18.1,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. CWS@LAA Spring Training. Not graded."},
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Darren Raddysh (FLAGGED body)",
     "market":"u2.5 Shots on Goal","line":"2.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":21.1,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED in slip body + NHL POD. TBL@VAN not found Mar 20."},
    {"date":"2026-03-20","sport":"NHL","market_type":"PLAYER_PROP","player_or_team":"Macklin Celebrini",
     "market":"u3.5 Shots on Goal","line":"3.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":15.5,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. BUF@SJS not found Mar 20."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Derrick Jr.",
     "market":"u1.5 Shots on Target","line":"1.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":45.6,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Toronto FC MLS. Not verified."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Timo Werner",
     "market":"u1.5 Shots on Target","line":"1.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":45.5,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. San Jose Earthquakes MLS. Not verified."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Abdon Prats",
     "market":"u1.5 Shots on Target","line":"1.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":45.5,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Mallorca. Not verified."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Alexander Prass",
     "market":"u1.5 Shots on Target","line":"1.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":45.4,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Hoffenheim lost 5-0 to Leipzig. Not a pick."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Luis Diaz",
     "market":"u1.5 Goals","line":"1.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":45.4,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Bayern game. Not verified."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Jandro Garcia",
     "market":"u0.5 Goals","line":"0.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":44.3,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Mallorca. Not verified."},
    {"date":"2026-03-20","sport":"SOCCER","market_type":"PLAYER_PROP","player_or_team":"Domingo Blanco",
     "market":"u0.5 Goals","line":"0.5","direction":"UNDER","units":0,"tier":"FLAGGED",
     "ev_pct":44.1,"is_pod":False,"pod_sport":None,"status":"PENDING","actual_val":None,
     "result_value":0,"result_source":None,"notes":"FLAGGED edge >15%. Tijuana Liga MX. Not verified."},
]

all_picks = picks + flagged

# ── COMPUTE SUMMARY ────────────────────────────────────────────────────────────
graded  = [p for p in picks if p["status"] in ("WIN","LOSS","PUSH")]
wins    = [p for p in graded if p["status"] == "WIN"]
losses  = [p for p in graded if p["status"] == "LOSS"]
pending = [p for p in picks  if p["status"] == "PENDING"]

units_won  = sum(p["result_value"] for p in wins   if p["result_value"] is not None)
units_lost = sum(p["result_value"] for p in losses if p["result_value"] is not None)
net = round(units_won + units_lost, 2)

by_sport = {}
for p in graded:
    s = p["sport"]
    if s not in by_sport:
        by_sport[s] = {"w": 0, "l": 0, "p": 0, "units": 0.0}
    rv = p["result_value"] or 0.0
    if p["status"] == "WIN":
        by_sport[s]["w"] += 1; by_sport[s]["units"] = round(by_sport[s]["units"] + rv, 2)
    elif p["status"] == "LOSS":
        by_sport[s]["l"] += 1; by_sport[s]["units"] = round(by_sport[s]["units"] + rv, 2)

pods_graded = [p for p in picks if p.get("is_pod") and p["status"] in ("WIN","LOSS","PUSH","PENDING")]
pod_summary_list = [{"sport": p["pod_sport"], "pick": p["player_or_team"]+" "+p["market"],
                     "status": p["status"], "units_result": p.get("result_value")} for p in pods_graded]

summary = {
    "date": "2026-03-20",
    "total_official_picks": len(picks),
    "total_flagged_picks":  len(flagged),
    "total_all":            len(all_picks),
    "graded":               len(graded),
    "pending":              len(pending),
    "wlp":                  f"{len(wins)}-{len(losses)}-0",
    "units_net":            net,
    "by_sport":             by_sport,
    "pod_results":          pod_summary_list,
    "luis_gil_mlb_pod":     "WIN — REINSTATED (K=7 vs 3.5 line, Bug #001)",
    "pending_picks":        [p["player_or_team"]+" "+p["market"] for p in pending],
    "generated_at":         datetime.now(timezone.utc).isoformat(),
    "grading_note": (
        "5 NHL games from slip (UTA@VGK, BUF@SJS, TBL@VAN, PHI@LAK) not found in "
        "NHL API for 2026-03-20 — schedule mismatch in model data. "
        "Liverpool/Chelsea soccer picks are EPL 2026-03-21. "
        "Real Madrid POD is La Liga 2026-03-22."
    ),
}

# ── MODEL RECORD ──────────────────────────────────────────────────────────────
total_risk = sum(p["units"] for p in graded)
model_record = {
    "last_updated": datetime.now(timezone.utc).isoformat(),
    "summary": {
        "w": len(wins), "l": len(losses), "p": 0,
        "units": net,
        "roi_pct": round(net / total_risk * 100, 1) if total_risk else 0.0,
    },
    "by_sport": by_sport,
    "by_tier":  {},
    "by_ev_bucket": {"2-4%": {}, "4-7%": {}, "7-12%": {}, "12%+": {}},
    "history": [
        {"date": p["date"], "pick": p["player_or_team"]+" "+p["market"],
         "sport": p["sport"], "tier": p["tier"], "units": p["units"],
         "status": p["status"], "result_value": p["result_value"], "ev_pct": p["ev_pct"]}
        for p in graded
    ],
}
for p in graded:
    t = p["tier"]
    if t not in model_record["by_tier"]:
        model_record["by_tier"][t] = {"w": 0, "l": 0, "p": 0, "units": 0.0}
    rv = p["result_value"] or 0.0
    if p["status"] == "WIN":
        model_record["by_tier"][t]["w"] += 1
        model_record["by_tier"][t]["units"] = round(model_record["by_tier"][t]["units"] + rv, 2)
    elif p["status"] == "LOSS":
        model_record["by_tier"][t]["l"] += 1
        model_record["by_tier"][t]["units"] = round(model_record["by_tier"][t]["units"] + rv, 2)

# ── POD RECORD ─────────────────────────────────────────────────────────────────
pod_record = {}
for p in [x for x in picks if x.get("is_pod")]:
    key = p["pod_sport"]
    if key not in pod_record:
        pod_record[key] = {"w": 0, "l": 0, "p": 0, "roi_pct": 0.0, "units_net": 0.0,
                           "streak_wl": {"type": None, "count": 0},
                           "streak_units": {"direction": None, "amount": 0.0},
                           "history": []}
    entry = {"date": p["date"], "pick": p["player_or_team"]+" "+p["market"],
             "status": p["status"], "units": p["units"], "result_value": p["result_value"]}
    pod_record[key]["history"].append(entry)
    rv = p["result_value"] or 0.0
    if p["status"] == "WIN":
        pod_record[key]["w"] += 1; pod_record[key]["units_net"] = round(pod_record[key]["units_net"] + rv, 2)
        pod_record[key]["streak_wl"] = {"type": "W", "count": 1}
        pod_record[key]["streak_units"] = {"direction": "positive", "amount": rv}
    elif p["status"] == "LOSS":
        pod_record[key]["l"] += 1; pod_record[key]["units_net"] = round(pod_record[key]["units_net"] + rv, 2)
        pod_record[key]["streak_wl"] = {"type": "L", "count": 1}
    total_risk_pod = sum(e["units"] for e in pod_record[key]["history"] if e["status"] in ("WIN","LOSS"))
    pod_record[key]["roi_pct"] = round(pod_record[key]["units_net"] / total_risk_pod * 100, 1) if total_risk_pod else 0.0

# ── WRITE ALL FILES ────────────────────────────────────────────────────────────
files_written = []

path = os.path.join(RESULTS, "2026-03-20_graded_slip.json")
with open(path, "w") as f: json.dump(all_picks, f, indent=2)
files_written.append(path)

path = os.path.join(RESULTS, "2026-03-20_summary.json")
with open(path, "w") as f: json.dump(summary, f, indent=2)
files_written.append(path)

path = os.path.join(RESULTS, "model_record.json")
with open(path, "w") as f: json.dump(model_record, f, indent=2)
files_written.append(path)

path = os.path.join(RESULTS, "pod_record.json")
with open(path, "w") as f: json.dump(pod_record, f, indent=2)
files_written.append(path)

# ── TERMINAL SUMMARY ──────────────────────────────────────────────────────────
print()
print("=" * 62)
print(f"EyeBlackIQ — Day Summary: {summary['date']}")
print("=" * 62)
print(f"Official picks:  {len(picks)}")
print(f"Flagged picks:   {len(flagged)}")
print(f"Total in file:   {len(all_picks)}")
print(f"Graded:          {len(graded)}  ({len(wins)}W - {len(losses)}L - 0P)")
print(f"Pending:         {len(pending)}")
print(f"Units net (graded only): {net:+.2f}u")
print()
print("By sport (graded picks):")
for sp, d in by_sport.items():
    print(f"  {sp:<8}: {d['w']}W - {d['l']}L   {d['units']:+.2f}u")
print()
print("POD Results:")
for p in pod_summary_list:
    rv = p['units_result']
    rv_str = f"{rv:+.2f}u" if rv is not None else "PENDING"
    print(f"  {p['sport']:<12}: {p['status']:<8}  {rv_str}")
print()
print("Luis Gil (MLB_POD): WIN — REINSTATED — K=7 vs 3.5 line")
print()
print(f"PENDING ({len(pending)} picks):")
for name in summary["pending_picks"]:
    print(f"  - {name}")
print()
print("Files written:")
for f in files_written:
    print(f"  {f}")
print("=" * 62)

if __name__ == "__main__":
    pass  # all work done at import time for direct execution
