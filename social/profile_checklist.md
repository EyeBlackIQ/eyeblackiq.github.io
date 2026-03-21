# EyeBlackIQ — Twitter/X Profile Checklist

*Last updated: 2026-03-21*

---

## Bio Copy (160 char max)

**Recommended:**
```
Quantitative multi-sport prediction model. ELO + ISR + 5-gate signal filter. NCAA ⚾ MLB ⚾ NHL 🏒 Soccer ⚽ | Paper trading since Mar 21 '26
```
(144 chars)

**Alternative (shorter):**
```
Data-driven multi-sport picks. ELO + ISR. 5-gate signal filter. Full methodology published. NCAA | MLB | NHL | Soccer
```
(118 chars)

---

## Pinned Tweet Template

Post this as your first substantive tweet and pin it:

```
What is EyeBlackIQ?

A quantitative model that finds pricing inefficiencies in sports markets.

→ Two independent rating systems (ELO + ISR)
→ 5-gate signal filter — all 5 must pass
→ Quarter-Kelly sizing — no guessing on stakes
→ Full methodology published at [SITE_URL]

Every pick posted with edge %, tier, and line at time of signal.
Every result logged publicly — wins AND losses.

This is the track record from day one.
```

---

## Hashtag Strategy

**Primary hashtags (use on daily picks posts):**
- `#SportsPrediction`
- `#NCAABaseball` (when NCAA picks posted)
- `#NHLPicks` (when NHL picks posted)
- `#MLBPicks` (when MLB picks posted)
- `#ModelPicks`

**Secondary hashtags (use occasionally):**
- `#QuantitativeSports`
- `#SportsAnalytics`
- `#CollegeBaseball`
- `#EdgeBeatsLuck`

**Avoid:**
- `#SportsBetting` — language policy
- `#Gambling` — language policy
- `#FreePicks` — positions you as a capper, not a model

---

## Posting Frequency

| Time | Content |
|---|---|
| ~8 AM ET | Daily picks post (via `run_morning_publish.py`) |
| ~11 PM ET | Day results post (via `run_evening.py`) |
| Weekly | Model record summary with notable wins/losses |
| As needed | Educational thread on methodology, ELO/ISR explanation |

---

## Profile Image / Banner

**Profile image:**
- Dark background (matte black `#0D0D0D`)
- "EB" in Bebas Neue font, Cherry Red `#DC143C`
- High contrast, readable at 48px
- Manual upload required — cannot be automated

**Banner image (1500×500px):**
- Dark matte black background
- "EyeBlackIQ" in large Bebas Neue
- Tagline: "The model sees what the market misses."
- Record bar (can be updated manually each week)
- Manual upload required

---

## Manual Upload Steps

1. Go to https://x.com/EyeBlackIQ
2. Click "Edit Profile"
3. Upload profile image (square, min 400×400px)
4. Upload banner image (1500×500px recommended)
5. Paste bio copy above
6. Website: https://eyeblackiq.github.io
7. Pin the first tweet (from template above)

---

## Config Notes

Twitter API keys needed in `.env`:
```
TWITTER_API_KEY=
TWITTER_API_SECRET=
TWITTER_ACCESS_TOKEN=
TWITTER_ACCESS_TOKEN_SECRET=
TWITTER_BEARER_TOKEN=
TWITTER_ENABLED=true
SITE_URL=https://eyeblackiq.github.io
```

OAuth 1.0a User Context is required for posting tweets. Apply for Elevated Access at developer.twitter.com if posting fails with Basic tier.
