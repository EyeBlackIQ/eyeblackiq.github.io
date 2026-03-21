# EyeBlackIQ — Investment Diligence Memo

**Date:** March 21, 2026
**Stage:** Pre-seed / Friends & Family
**Category:** Sports prediction / quantitative modeling
**Status:** Active paper trading — NCAA Baseball live, multi-sport in validation

---

## Executive Summary

EyeBlackIQ is a quantitative multi-sport prediction model that identifies pricing inefficiencies in sports markets. The model uses Elo ratings, Iterative Strength Ratings (ISR), 5-gate signal filtering, and Quarter-Kelly sizing across NCAA Baseball, MLB, NHL, and Soccer.

**Early results (paper trading, 9 graded plays as of Mar 21):**
- Record: 6W-3L-0P
- Net units: +3.38u
- ROI: +24.1%
- Sample size: too small for statistical significance (n=9)

**Investment thesis:** The opportunity is in systematic edge identification at scale, transparency as a brand moat, and a flywheel where track record drives subscriber revenue.

---

## Model Edge Assessment

### Methodology
The model computes win probability via two independent systems (Elo + ISR), blends them (60/40), applies SP ERA adjustment for baseball, then compares to no-vig market probability. Edge = Model% − Market%.

### 5-Gate Signal Filter
All five gates must pass in sequence. Any failure blocks the signal:
1. Pythagorean gate (team performance vs. expected)
2. Edge ≥ 3% above no-vig market probability
3. Elo and ISR models agree within 15pp
4. Line has not moved >0.5 units sharp-direction against model
5. ETL data timestamp < 4 hours old

### Critical Risk: K=6.0 Logistic Steepness
The Elo win probability formula `P = 1/(1+10^(-Δ/400))` uses a divisor of 400 (equivalent to K=6.0 logistic steepness). This was calibrated on chess data. For NCAA Baseball:

- Traditional 400-divisor may **over-compress** win probabilities in high-variance sports
- A 200-point Elo gap produces ~76% win probability — but NCAA Baseball game-level variance (run differential, pitching randomness) may mean the true win% is closer to 65%
- **Overconfident probabilities inflate edge calculations artificially**
- Mitigation: the 5-gate filter (particularly gate 3 — model agreement) catches cases where Elo and ISR diverge significantly, which often correlates with overfit signals

**Recommendation:** Run calibration bins (predicted probability vs. actual win rate) across 500+ graded games before reducing the divisor. The current early-season sample (n=9) is insufficient.

### Strengths
- ISR (Iterative Strength Ratings) provides a data-independent check on Elo that reduces single-model overfit
- SP ERA adjustment adds a material signal layer absent from pure-ratings models
- Gate 2 (3% minimum edge) filters out noise by requiring a minimum market inefficiency
- Walk-forward only backtesting discipline (no lookahead)

### Weaknesses
- NCAA Baseball has high variance (7-inning games early season, cold weather, freshman pitchers)
- n=9 graded results: too small to distinguish skill from variance. 95% confidence interval on 67% win rate spans approximately 35% to 90%
- No historical odds data yet for backtesting NCAA Baseball at scale (SBR files not yet downloaded)
- Hockey and soccer models are not yet validated

---

## Data Infrastructure

### Current State
| Source | Status | Coverage |
|---|---|---|
| ESPN APIs (NCAA, MLB, NHL, Soccer) | Working | Schedules + results |
| MLB Stats API | Working | Player stats, schedules |
| NHL Official API | Working | Schedule, player game logs |
| Club Elo API | Working | Historical Elo 1939+ |
| ISR CSV files (Downloads) | Available | 2023–2026 NCAA |
| Pitcher ERA database | Available | 2026 Week 5 |
| TheRundown API | Available (key in .env) | Live odds + Pinnacle |

### Missing (Needed for Full Backtesting)
- SBR historical odds for MLB and NHL (manual download required)
- football-data.co.uk CSV files for soccer (manual download required)
- MoneyPuck NHL xG CSVs (manual download required)
- pybaseball Statcast pulls (pip install required)

### Infrastructure Quality
- SQLite database with signals + results tables
- Walk-forward export pipeline (export.py → JSON → GitHub Pages)
- Automated grading pipeline
- Kill switch monitoring (DrawdownMonitor class)
- ETL logging (etl_log table)

---

## Product

### Website
- GitHub Pages deployment (eyeblackiq.github.io)
- Dark-theme sports analytics aesthetic
- Filter bar: sport + tier + PODs Only
- POD (Pick of the Day) feature with gold highlight
- Full results page with loss analysis toggle
- Methodology page with model transparency

### Daily Workflow
1. `run_morning.py` — fetch schedule → generate signals → export JSON
2. `approve_pod.py` — human reviews and approves POD pick
3. `run_morning_publish.py` — git push to GitHub Pages → Twitter post
4. `run_evening.py` — grade results → update records → push

### Twitter
- Account: @EyeBlackIQ
- Post formatter built (`social/twitter_post.py`) — not yet live (keys needed)

---

## Competitive Moat

### Differentiators
1. **Transparent methodology:** Full formula documentation, calibration target (±2%), no black-box claims
2. **Five-gate filtering:** Explicit signal discipline that most public cappers don't employ
3. **POD system:** One per-sport high-conviction pick per day — focuses attention and builds a trackable record
4. **Multi-sport:** Single model architecture spanning 4+ sports reduces single-sport variance
5. **No volume cap:** Posts all qualifying edge plays, letting followers choose their own unit sizing

### Moat Quality Assessment
- **Weak moat today:** The Elo + ISR model is replicable by any quant with 4 hours of work. The data sources (ESPN, Club Elo, MLB API) are all free and public.
- **Moat building over time:** Track record (CLV + calibration over 1,000+ graded plays) is hard to fake and takes 12–18 months to establish. This is the real moat.
- **Brand moat:** "The model sees what the market misses" + transparent methodology + consistent voice differentiates from 95% of sports prediction accounts which have no documented methodology.

---

## Critical Gaps (≥8 Required)

1. **Sample size:** 9 graded plays. Statistical significance requires 300–500 minimum.
2. **Backtesting:** No historical odds data loaded for any sport. Cannot validate edge historically.
3. **Hockey model:** NHL model exists in code but no validation data loaded.
4. **Soccer model:** Soccer model exists but Club Elo + football-data.co.uk pipeline not complete.
5. **MLB model:** MLB model exists but Statcast/pybaseball not yet integrated.
6. **Closing line benchmark:** CLV tracking requires Pinnacle closing line data. Not yet systematically logged.
7. **Logistic steepness calibration:** K=6.0 divisor (400) may be miscalibrated for NCAA Baseball.
8. **Schedule validation:** Bug #002 showed NHL schedule mismatch — no cross-validation between model schedule and official API schedule exists.
9. **Twitter integration:** Post formatter built but no API keys configured. No audience yet.
10. **Subscriber monetization:** No revenue mechanism exists. Pure audience play currently.

---

## 90-Day Roadmap

### Days 1–30 (March 21 – April 21)
- Complete NCAA Baseball paper trading through end of regular season
- Download SBR historical odds for MLB + NHL (prerequisite for backtesting)
- Download football-data.co.uk CSVs for soccer
- Fix schedule validation bug (NHL schedule cross-check)
- Reach 50+ graded NCAA Baseball plays
- Target: first CLV positive reading (need 20+ plays with closing lines logged)

### Days 31–60 (April 21 – May 21)
- MLB season begins April 1 — start MLB paper trading immediately
- Run historical backtest on 3 seasons of NCAA Baseball (requires SBR odds)
- Calibration bin analysis: compare predicted win% to actual win% across 100+ NCAA plays
- Achieve 100+ graded NCAA plays
- Twitter account: first 500 followers target

### Days 61–90 (May 21 – June 21)
- NHL playoffs: high-volume validation window for NHL model
- MLB model: Statcast integration for pitcher strikeout props
- Go-live assessment: if NCAA backtest ROI > 3% + CLV ≥ 55% + calibration ±2%, consider going live NCAA Baseball
- Soccer: Euro season ends, prepare for summer leagues
- 500+ graded plays across all sports (prerequisite for any go-live decision)

---

## Investment Thesis

**Bull case:** A systematic, transparent, multi-sport prediction model with a documented go-live process and three layers of public accountability (picks, results, methodology) can build a loyal subscriber base of 1,000–10,000 followers. At $25–$50/month, 500 subscribers = $12,500–$25,000 MRR.

**Bear case:** Sports prediction is a highly competitive, crowded market. Free picks are abundant. Monetization requires either real-money proof-of-concept (not yet validated) or a large enough subscriber base to support premium access. Getting there requires 12+ months of consistent, high-quality execution.

**Key metrics to watch:**
1. CLV% at 300+ graded plays (target: ≥55%)
2. Calibration bins at 500+ plays (target: ±2%)
3. Twitter follower growth trajectory (target: 500 followers by 60 days)
4. Website unique visitors per day (target: 100+ daily)

**Current recommendation:** Continue paper trading through the go-live thresholds. The model architecture is sound, the infrastructure is well-built, and the transparency philosophy is differentiated. Do not go live until CLV and calibration thresholds are cleared.
