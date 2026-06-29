"""
core/recruitability_engine.py — FHire Recruitability Score (Dimension 3, 25%)

WHY THIS FILE EXISTS:
    "Can we ACTUALLY hire this person?"

    A candidate who is perfect on paper — 10/10 capability, 10/10 trajectory —
    but hasn't logged in for 6 months and has a 5% recruiter response rate is
    NOT actually available. The JD said this explicitly.

    This engine produces TWO outputs:
        1. recruitability_score  (0-100): How recruitable is this person?
        2. recruitability_multiplier (0.1-1.0): Applied to the base score
           in the final formula. This is MULTIPLICATIVE, not additive.

    WHY MULTIPLICATIVE:
        Additive formula: base_score = cap*0.40 + traj*0.25 + recr*0.25 + auth*0.10
        → A highly capable but totally unavailable candidate still scores ~65/100.
        Multiplicative formula: final = base * multiplier
        → That same candidate with multiplier=0.1 → final score drops to ~6.5/100.
        → They fall OUT of the top 100. Exactly what the JD wanted.

    THREE COMPONENTS:
        Availability (40 pts):  Is this person actually looking / recently active?
        Responsiveness (35 pts): Will they reply to us? (percentile-based)
        Logistics (25 pts):     Can they start soon and work in-office?

    All percentile calculations use pre-computed distributions from precompute.py.
    No magic numbers — every number is defensible as "Xth percentile of 100K."

HOW IT CONNECTS:
    Called from pipeline.py and rank.py as:
        recr = recruitability_score_and_multiplier(candidate, signal_distributions)
    Returns dict with: score, multiplier, breakdown
"""

from datetime import date, datetime
from typing import Any

from core.percentile import to_percentile, to_percentile_inverted

# Hackathon reference date — used for recency calculations throughout
TODAY: date = date(2026, 6, 25)

# Location tiers as specified in the master plan
# Tier 1: JD company office locations (best fit for commute/hybrid)
_TIER1_LOCATIONS: list[str] = ["pune", "noida"]

# Tier 2: Major Indian tech hubs (easy relocation, same culture)
_TIER2_LOCATIONS: list[str] = [
    "hyderabad", "mumbai", "delhi", "bangalore",
    "bengaluru", "gurgaon", "gurugram", "ncr",
]


# ─── COMPONENT 1: AVAILABILITY (max 40 points) ────────────────────────────────

def _availability_score(signals: dict[str, Any]) -> float:
    """
    Measures whether the candidate is actually reachable and looking.

    Two sub-signals:
        open_to_work_flag (+15): Actively signalled they want to be contacted.
        last_active_date  (+25): How recently they used the platform.
            ≤7 days   → 25 pts (very recently active)
            ≤30 days  → 20 pts (active this month)
            ≤90 days  → 12 pts (active this quarter)
            ≤180 days →  4 pts (active within 6 months, weak signal)
            >180 days →  0 pts (dormant — JD said to down-weight heavily)

    Returns:
        float 0-40
    """
    score: float = 0.0

    # Open-to-work flag
    if signals.get("open_to_work_flag", False):
        score += 15.0

    # Activity recency
    raw_last_active = signals.get("last_active_date", "2020-01-01")
    try:
        last_active = datetime.strptime(str(raw_last_active), "%Y-%m-%d").date()
        days_inactive = (TODAY - last_active).days
    except (ValueError, TypeError):
        days_inactive = 365  # Unknown → assume stale

    if days_inactive <= 7:
        score += 25.0
    elif days_inactive <= 30:
        score += 20.0
    elif days_inactive <= 90:
        score += 12.0
    elif days_inactive <= 180:
        score += 4.0
    # 180+ days → 0 extra points

    return min(40.0, score)


# ─── COMPONENT 2: RESPONSIVENESS (max 35 points) ─────────────────────────────

def _responsiveness_score(signals: dict[str, Any], signal_distributions: dict) -> float:
    """
    Measures how likely this candidate is to respond to recruiter outreach.
    All three sub-signals are percentile-based for full academic defensibility.

    Sub-signals:
        recruiter_response_rate   (18 pts max): Do they reply to recruiters?
        interview_completion_rate (10 pts max): Do they show up to interviews?
        avg_response_time_hours   ( 7 pts max): How quickly do they reply?
                                                Inverted — lower is better.

    Returns:
        float 0-35
    """
    score: float = 0.0

    # Recruiter response rate — percentile, higher = better
    rr = signals.get("recruiter_response_rate", 0.3)
    rr_pct = to_percentile(float(rr), "recruiter_response_rate", signal_distributions)
    score += (rr_pct / 100.0) * 18.0   # Max 18 pts

    # Interview completion rate — percentile, higher = better
    icr = signals.get("interview_completion_rate", 0.5)
    icr_pct = to_percentile(float(icr), "interview_completion_rate", signal_distributions)
    score += (icr_pct / 100.0) * 10.0  # Max 10 pts

    # Average response time — INVERTED percentile (lower hours = better)
    art = signals.get("avg_response_time_hours", 48.0)
    art_pct = to_percentile_inverted(float(art), "avg_response_time_hours", signal_distributions)
    score += (art_pct / 100.0) * 7.0   # Max 7 pts

    return min(35.0, score)


# ─── COMPONENT 3: LOGISTICS (max 25 points) ───────────────────────────────────

def _logistics_score(
    signals: dict[str, Any],
    profile: dict[str, Any],
    signal_distributions: dict,
) -> float:
    """
    Measures practical hiring friction: location, notice period, work mode.

    Sub-signals:
        Location    (12 pts max): Tier 1 > Tier 2 > India-relocation > overseas
        Notice period (8 pts max): Inverted percentile — shorter is better.
        Work mode    (5 pts max): Hybrid/flexible > onsite > remote.

    Returns:
        float 0-25
    """
    score: float = 0.0

    # ── Location ──────────────────────────────────────────────────────────────
    country = profile.get("country", "")
    loc = profile.get("location", "").lower()

    if country == "India":
        if any(city in loc for city in _TIER1_LOCATIONS):
            score += 12.0  # Best: already in JD's city
        elif any(city in loc for city in _TIER2_LOCATIONS):
            score += 9.0   # Good: major tech hub, easy to relocate
        elif signals.get("willing_to_relocate", False):
            score += 5.0   # Elsewhere in India but willing to move
        else:
            score += 2.0   # India but unknown/small city, not willing to relocate
    elif signals.get("willing_to_relocate", False):
        score += 3.0       # Overseas but willing to relocate (visa risk)
    # Overseas + not willing to relocate → 0 pts

    # ── Notice period — inverted percentile ───────────────────────────────────
    notice = signals.get("notice_period_days", 60)
    notice_pct = to_percentile_inverted(
        float(notice), "notice_period_days", signal_distributions
    )
    score += (notice_pct / 100.0) * 8.0   # Max 8 pts

    # ── Work mode preference ──────────────────────────────────────────────────
    mode = signals.get("preferred_work_mode", "").lower()
    if mode in ("hybrid", "flexible"):
        score += 5.0   # Matches typical Series A office setup
    elif mode == "onsite":
        score += 3.0   # Fine — no friction there
    elif mode == "remote":
        score += 1.0   # JD prefers hybrid/onsite

    return min(25.0, score)


# ─── MULTIPLIER CONVERSION ────────────────────────────────────────────────────

def _score_to_multiplier(raw_score: float) -> float:
    """
    Convert raw recruitability score (0-100) to a multiplier (0.1-1.0).

    Floor of 0.1 ensures even the worst candidate doesn't get zeroed out
    entirely — signals can be incomplete or stale, not necessarily a red flag.

    Linear mapping: 0 → 0.10, 100 → 1.00
    """
    return 0.10 + (max(0.0, min(100.0, raw_score)) / 100.0) * 0.90


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def recruitability_score_and_multiplier(
    candidate: dict,
    signal_distributions: dict,
) -> dict:
    """
    Compute the full recruitability score and multiplier for a single candidate.

    This is the function called by pipeline.py and rank.py.

    Args:
        candidate:            Single candidate dict from candidates.jsonl
        signal_distributions: Pre-loaded distributions dict (from distributions.json)
                              Used for percentile calculations.

    Returns:
        {
            "score":      float 0-100   — raw recruitability score
            "multiplier": float 0.1-1.0 — applied to final base score
            "breakdown": {
                "availability":    float 0-40,
                "responsiveness":  float 0-35,
                "logistics":       float 0-25,
            }
        }
    """
    signals: dict[str, Any] = candidate.get("redrob_signals", {})
    profile: dict[str, Any] = candidate.get("profile", {})

    avail = _availability_score(signals)
    resp = _responsiveness_score(signals, signal_distributions)
    logi = _logistics_score(signals, profile, signal_distributions)

    raw_score = avail + resp + logi   # 0-100
    multiplier = _score_to_multiplier(raw_score)

    return {
        "score": round(raw_score, 4),
        "multiplier": round(multiplier, 6),
        "breakdown": {
            "availability": round(avail, 4),
            "responsiveness": round(resp, 4),
            "logistics": round(logi, 4),
        },
    }
