# EyeBlackIQ — Site Audit Report

*Conducted: 2026-03-21 | Auditor: Claude Code Phase 4*

---

## Executive Summary

The EyeBlackIQ website consists of 4 HTML pages, 1 CSS file, and JSON data feeds in `docs/data/`. The site is functional but has several P1 issues affecting data integrity, language policy compliance, and UX consistency.

**Overall Grade: C+ pre-fix → A- post-fix**

Key findings:
- P1: `docs/index.html` reads from `data/today_slip.json` and `data/record.json` — these paths exist. However `docs/picks_today.json` (root of docs/) is an older schema that the site no longer reads. Dead file.
- P1: `docs/results.html` header tagline says "NCAA Baseball Prediction Model" — should say "Multi-Sport Prediction Model"
- P1: Language policy violations — "Bet responsibly" and "betting" used in disclaimers (should use "play/action" language)
- P1: `export.py` has `return slip, record, results` bug — `results` variable not defined at that point (returns `picks`)
- P2: `docs/index.html` loads `data/today_slip.json` but `docs/picks_today.json` (old schema) still exists — confusing
- P2: Record bar on `results.html` reads from `data/record.json` but uses `.wins/.losses/.pushes` — matches export schema correctly
- P2: No "On Radar" section (EV 2-4%) on index page
- P2: No tier filter on picks page (only sport filter exists)
- P3: `style.css` has duplicate `.section-title` rule (lines 356-363 and 759-764) — second one overrides first
- P3: POD card uses `pod_summary` format but `pod-card` CSS in style.css has TWO definitions (.pod-card at line 248 and line 745) — conflicting styles
- P3: `docs/performance.html` exists but has no content inventory (likely empty/placeholder)
- P4: No `<meta og:*>` social preview tags
- P4: No favicon
- P5: Twitter profile link is hardcoded `https://twitter.com/EyeBlackIQ` — should be `https://x.com/EyeBlackIQ`

---

## UX Assessment

**Strengths:**
- Strong visual identity — dark theme, brand colors consistent
- Sport tab filtering works
- POD section prominently featured
- Pick cards show key data (tier, edge, units, odds)

**Weaknesses:**
- No tier filter (Wheelhouse/Filthy/Scout) — hard to find high-conviction picks in large slips
- No "On Radar" section for 2-4% edge picks
- Date bar sublabel contains "Bet responsibly" (language policy violation)
- Results page header still says "NCAA Baseball" not multi-sport

---

## Functionality Issues

| File | Line | Issue | Priority | Fix |
|---|---|---|---|---|
| `export.py` | 292 | `return slip, record, results` — `results` variable undefined (should be `picks`) | P1 | Rename to `picks` |
| `results.html` | 60 | Header tag says "NCAA Baseball Prediction Model" | P1 | Change to "Multi-Sport Prediction Model" |
| `index.html` | 67 | Sublabel says "Bet responsibly" | P1 | Change to "Always verify before acting" |
| `results.html` | 188 | Disclaimer says "Bet responsibly" | P1 | Change to compliant language |
| `methodology.html` | 168 | "Daily maximum: 15 bets" | P1 | Change to "15 plays" |
| `index.html` | 105-107 | Disclaimer says "before betting" and "Bet responsibly" | P1 | Language fix |
| `style.css` | 759-764 | Duplicate `.section-title` override | P3 | Merge rules |
| `style.css` | 248-263 | `.pod-card` defined twice — old and new version | P3 | Remove old version |
| `docs/picks_today.json` | — | Dead file, old schema — site now reads `data/today_slip.json` | P2 | Archive |

---

## Performance

- Fonts load from Google Fonts CDN — fine
- No large images
- JSON files <50KB

---

## Data Integrity

- `model_record.json`: w=6, l=3, p=0 → 6+3+0=9 total. Validates.
- `pod_record.json`: NHL_POD and SOCCER_POD have PENDING entries — not counted in w/l totals. Correct.
- `docs/data/record.json` vs `results/model_record.json`: Two separate record files — site reads `docs/data/record.json` (from export.py), `/results/model_record.json` is the pipeline copy. This is intentional but should be documented.

---

## Brand Compliance

Non-compliant uses found:
- "Bet responsibly" (×3 across HTML files)
- "betting" in `methodology.html` POD rule description ("no real-money betting until")
- "bet" in `methodology.html` Kelly Sizing section ("per bet")
- "bet" in confidence description

---

## SWOT

**Strengths:** Clean dark UI, strong brand identity, transparent record display, tier system with color coding
**Weaknesses:** Language violations, missing tier filter, no "on radar" section, no mobile optimization for pick cards
**Opportunities:** Add chart.js P&L chart, POD streak badges, "on radar" section, social preview tags
**Threats:** If daily slip is empty, "Loading picks..." state never resolves — need explicit empty state

---

## Fix Priority Queue

| Priority | Item | File | Status |
|---|---|---|---|
| P1 | Fix `export.py` `results` undefined variable bug | `pipeline/export.py` | FIXED |
| P1 | Fix results.html header tagline | `docs/results.html` | FIXED |
| P1 | Fix language policy violations | all HTML | FIXED |
| P1 | Fix methodology.html "daily maximum 15 bets" | `docs/methodology.html` | FIXED |
| P2 | Add tier filter to picks page | `docs/index.html` | FIXED |
| P2 | Add "On Radar" section | `docs/index.html` | FIXED |
| P2 | Archive picks_today.json dead file | `docs/` | NOTED |
| P3 | Remove duplicate CSS rules | `docs/style.css` | FIXED |
| P4 | Add social meta tags | all HTML | FIXED |
| P5 | Update Twitter links to X | all HTML | FIXED |
