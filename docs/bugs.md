# EyeBlackIQ — Bug Log

---

## Bug #001 — POD Omission from Slip
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** HIGH — POD is the brand's flagship pick. Omitting it from the daily slip is contradictory and damages trust.

**Root cause:**
`slip.py` (or equivalent generator) placed Luis Gil Over 3.5 Strikeouts in the `FLAGGED` section (edge >15%) rather than enforcing the POD guarantee. The POD selection correctly identified Gil as MLB_POD, but the daily slip body's `K_OVERS` section output `(no signals)` — indicating the edge filter blocked it before the POD override was applied.

The bug: **POD selection ran before the edge gate, but the slip body printed the gated (filtered) list rather than the POD-guaranteed list.**

**Fix applied:**
1. `pipeline/grade_mar20.py` manually reinstates Luis Gil as MLB_POD with `is_pod=True`
2. Phase 3 rewrite of `slip.py` adds final-step POD validation with hard assertion:
   ```python
   for sport, pod in pods.items():
       assert pod in final_slip, f"BUG: {sport} POD missing from slip"
   ```
3. POD is always the LAST operation in slip generation, running AFTER all edge gates

**Prevention:**
- Hard assert in slip.py post-POD-selection (raises exception, not silent omission)
- POD is guaranteed on the slip regardless of edge gate status
- Test added: `tests/test_pod_guarantee.py`

**Impact:**
- Luis Gil recorded 7 Ks (vs 3.5 line) — confirmed WIN at +2.68u
- POD guarantee feature would have correctly included this pick
- No real-money impact (paper trading phase)

---

## Bug #002 — NHL Schedule Mismatch (5 games not found)
**Date discovered:** 2026-03-21
**Date resolved:**   Unresolved — requires investigation
**Severity:** MEDIUM — 10 official picks and 1 NHL POD are PENDING due to incorrect game matchups

**Root cause:**
The EyeBlackIQ slip for 2026-03-20 listed these NHL games:
- BUF@SJS 7:30 PM ET
- TBL@VAN 10:00 PM ET
- PHI@LAK 10:30 PM ET
- UTA@VGK 10:00 PM ET

NHL API (`api-web.nhle.com/v1/score/2026-03-20`) shows only 5 games on that date:
CAR@TOR, NJD@WSH, COL@CHI, FLA@CGY, ANA@UTA — none matching the slip's last 4 games.

**Likely cause:** The schedule data source used by the model fetched the wrong date's games or used a cached/stale schedule. The March 21 NHL schedule includes BUF@LAK, PHI@SJS, TBL@EDM (similar but not identical to the slip's listings).

**Fix needed:**
1. Identify which schedule API the model uses and verify date alignment
2. Add schedule validation: cross-check model game matchups against official NHL API schedule before signal generation
3. Add ETL timestamp check: if schedule data > 6 hours old, re-fetch before generating picks

**Affected picks:** JJ Peterka, Rasmus Andersson, Jamie Drysdale, Alex Laferriere, Collin Graf, Victor Hedman, Shea Theodore, Rasmus Dahlin, Adrian Kempe, Darren Raddysh (NHL POD) — all PENDING

---

## Bug #003 — Soccer SOT picks for EPL Mar 21 games listed on Mar 20 slip
**Date discovered:** 2026-03-21
**Date resolved:**   Unresolved — by design or data error
**Severity:** LOW — picks are PENDING, not lost

**Root cause:**
Hugo Ekitiké (Liverpool) and Cole Palmer (Chelsea) SOT picks appeared on the March 20 slip, but their EPL games are on March 21 (Liverpool vs Brighton, Chelsea vs Everton). The model appears to have pulled the next available game for each player regardless of date alignment with the slip date.

**Fix needed:**
1. Add date filter to soccer prop generation: only include props for games matching the slip date
2. Or: clearly flag forward-looking soccer props with the actual game date

---

## Bug #004 — export.py `results` Variable Undefined
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** HIGH — `run_export()` returns `slip, record, results` but `results` is never defined; the variable holding graded picks is named `picks`. Would cause NameError on any code that calls `run_export()` and unpacks its return value.

**Root cause:**
In `pipeline/export.py` line 292, the return statement was `return slip, record, results` but the variable assigned at line 282 was `picks = export_results(50)`. The name `results` was never defined in `run_export()`.

**Fix applied:**
Changed `return slip, record, results` to `return slip, record, picks` in `pipeline/export.py`.

**Files modified:** `pipeline/export.py`

---

## Bug #005 — results.html Header Says "NCAA Baseball Prediction Model"
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** LOW — Branding inconsistency. Site covers multiple sports but header still says NCAA Baseball only.

**Root cause:**
`docs/results.html` logo-tag text was never updated after multi-sport expansion.

**Fix applied:**
Changed logo-tag to "Multi-Sport Prediction Model" in `docs/results.html` rebuild.

---

## Bug #006 — Language Policy Violations in HTML
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** MEDIUM — Compliance issue. "Bet responsibly", "betting", "per bet" appear in HTML despite standing language policy.

**Locations fixed:**
- `docs/index.html`: date bar sublabel, disclaimer
- `docs/results.html`: disclaimer
- `docs/methodology.html`: Kelly sizing section, go-live description, confidence section

**Fix applied:**
Replaced "Bet responsibly" with "Always verify before acting", "betting" with "trading/playing", "per bet" with "per play" across all rebuilt HTML files.

---

## Bug #007 — Duplicate CSS Rules in style.css
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** LOW — `.section-title` and `.pod-card` were each defined twice in the original style.css. Second definition silently overrode the first, making the first definition dead code.

**Fix applied:**
Rewrote `docs/style.css` with consolidated, non-duplicate rules. Removed all dead CSS.

---

## Bug #008 — export.py `r.line_val` Column Does Not Exist
**Date discovered:** 2026-03-21
**Date resolved:**   2026-03-21
**Severity:** HIGH — `export_results()` SELECT query referenced `r.line_val` which is not a column in the results table, causing `sqlite3.OperationalError: no such column: r.line_val` on every export run.

**Root cause:**
The results table schema uses `closing_line` for the line value at time of grading. The `export_results()` function in `pipeline/export.py` incorrectly used `r.line_val` in both the SELECT (line ~232) and the loss analysis builder (line ~248). This was a naming mismatch — the column was likely called `line_val` during early schema design and renamed to `closing_line` before the table was finalized.

**Fix applied:**
1. Changed `r.line_val` → `r.closing_line` in the SELECT query (line ~232)
2. Changed `r.get("line_val")` → `r.get("closing_line")` in the loss analysis builder (line ~248)

**Files modified:** `pipeline/export.py`

---
