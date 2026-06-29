"""
core/authenticity_engine.py — FHire Authenticity Score (Dimension 4, 10%)

WHY THIS FILE EXISTS:
    "Should we trust this profile?"

    The competition dataset contains ~80 honeypot candidates with deliberately
    fake signals — expert skills claimed with 0 months usage, impossible career
    durations. If any of these appear in our top 10, we are disqualified.

    The disqualifier handles the most obvious honeypots as a hard filter.
    This engine handles the SOFTER trust signals:
        - Skill inflation: claimed Expert but failed the assessment test
        - Suspicious pattern: 10+ expert skills but zero assessments taken
        - Profile completeness: thin profiles signal low engagement
        - Verification: email + phone verified adds a small trust bonus

    This engine also re-checks for honeypots as a safety net (paranoia is cheap
    here — returning score=0 immediately is very fast and doubly safe).

    Authenticity contributes 10% of base_score. It won't rocket a weak candidate
    to the top, but it WILL sink a fraudulent or low-trust profile.

HOW IT CONNECTS:
    Called from pipeline.py and rank.py as:
        auth = authenticity_score(candidate)
    Returns dict with: score (0-100), flags (list of strings)
"""

from typing import Any


# ─── CONSTANTS ────────────────────────────────────────────────────────────────

# Penalty for each detected skill inflation case (expert claimed, low test score)
_EXPERT_INFLATION_PENALTY: float = 20.0

# Penalty for advanced-level inflation
_ADVANCED_INFLATION_PENALTY: float = 10.0

# Bonus added per skill where assessment score is 80+
_ASSESSMENT_VALIDATION_BONUS: float = 5.0

# Cap on total assessment bonus (prevents over-rewarding test-takers)
_MAX_ASSESSMENT_BONUS: float = 15.0

# Threshold below which an "expert" claim is treated as inflated
_EXPERT_THRESHOLD: int = 50

# Threshold below which an "advanced" claim is treated as inflated
_ADVANCED_THRESHOLD: int = 30

# If candidate has this many or more expert skills with ZERO assessments, flag it
_SUSPICIOUS_EXPERT_COUNT: int = 10

# Profile completeness thresholds
_COMPLETENESS_PENALTY_THRESHOLD: float = 50.0
_COMPLETENESS_BONUS_THRESHOLD: float = 85.0
_COMPLETENESS_PENALTY: float = 15.0
_COMPLETENESS_BONUS: float = 5.0

# Verification bonus when both email and phone are verified
_VERIFICATION_BONUS: float = 5.0


# ─── HONEYPOT SAFETY-NET CHECKS ───────────────────────────────────────────────
# These mirror checks in disqualifier.py — belt-and-suspenders approach.
# disqualifier.py runs first and removes obvious honeypots; this catches any
# that slipped through or are evaluated outside the normal rank.py flow.

def _check_honeypot(
    skills: list[dict],
    career: list[dict],
    yoe: float,
) -> tuple[bool, str | None]:
    """
    Fast honeypot double-check.

    Returns:
        (True, reason) if honeypot detected → caller should return score=0
        (False, None)  if clean
    """
    # Check 1: expert skill with 0 months usage
    zero_experts = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 1) == 0
    )
    if zero_experts >= 3:
        return True, "HONEYPOT: 3+ expert skills with 0 months usage"

    # Check 2: career role lasting longer than total experience allows
    max_possible_months = (yoe * 12) + 18  # 18-month buffer
    for role in career:
        if role.get("duration_months", 0) > max_possible_months:
            return True, "HONEYPOT: career role duration exceeds total years of experience"

    return False, None


# ─── SKILL INFLATION DETECTION ────────────────────────────────────────────────

def _skill_inflation_check(
    skills: list[dict],
    assessments: dict[str, float],
) -> tuple[float, list[str]]:
    """
    Detect candidates who claim high proficiency but have low assessment scores.

    For each skill that has an assessment score:
        - Expert claimed + score < 50  → heavy penalty, flag it
        - Advanced claimed + score < 30 → moderate penalty, flag it
        - Score >= 80                   → validation bonus (capped)

    Args:
        skills:      List of skill dicts from candidate["skills"]
        assessments: Dict of skill_name → score (from redrob_signals)

    Returns:
        (delta_score, flags)
        delta_score: net adjustment (negative = penalty, positive = bonus)
        flags:       list of human-readable flag strings
    """
    delta: float = 0.0
    flags: list[str] = []
    bonus_accumulated: float = 0.0

    for skill in skills:
        name = skill.get("name", "")
        if name not in assessments:
            continue  # No assessment for this skill — skip

        ass_score = float(assessments[name])
        claimed = skill.get("proficiency", "")

        if claimed == "expert" and ass_score < _EXPERT_THRESHOLD:
            delta -= _EXPERT_INFLATION_PENALTY
            flags.append(
                f"skill_inflation: {name} — claimed expert, "
                f"assessment scored {ass_score:.0f}/100"
            )
        elif claimed == "advanced" and ass_score < _ADVANCED_THRESHOLD:
            delta -= _ADVANCED_INFLATION_PENALTY
            flags.append(
                f"skill_inflation: {name} — claimed advanced, "
                f"assessment scored {ass_score:.0f}/100"
            )
        elif ass_score >= 80.0:
            # Validate skill bonus — but cap total bonus
            if bonus_accumulated < _MAX_ASSESSMENT_BONUS:
                available = _MAX_ASSESSMENT_BONUS - bonus_accumulated
                to_add = min(_ASSESSMENT_VALIDATION_BONUS, available)
                delta += to_add
                bonus_accumulated += to_add

    return delta, flags


# ─── SUSPICIOUS PROFILE PATTERN ───────────────────────────────────────────────

def _suspicious_pattern_check(
    skills: list[dict],
    assessments: dict[str, float],
) -> tuple[float, list[str]]:
    """
    Flag candidates with an unusually high number of expert skills but
    zero assessments taken. Real experts tend to validate their claims.

    Returns:
        (delta_score, flags)
    """
    expert_count = sum(1 for s in skills if s.get("proficiency") == "expert")
    has_assessments = len(assessments) > 0

    if expert_count >= _SUSPICIOUS_EXPERT_COUNT and not has_assessments:
        return -20.0, [
            f"suspicious: {expert_count} expert skills claimed, "
            "zero assessments taken — unvalidated expertise"
        ]
    return 0.0, []


# ─── PROFILE COMPLETENESS ─────────────────────────────────────────────────────

def _completeness_check(signals: dict[str, Any]) -> tuple[float, list[str]]:
    """
    Thin profiles are harder to evaluate — penalise for low completeness,
    reward for high completeness.

    Returns:
        (delta_score, flags)
    """
    completeness = float(signals.get("profile_completeness_score", 60.0))
    flags: list[str] = []

    if completeness < _COMPLETENESS_PENALTY_THRESHOLD:
        flags.append(
            f"incomplete profile (completeness score: {completeness:.0f}/100)"
        )
        return -_COMPLETENESS_PENALTY, flags
    elif completeness >= _COMPLETENESS_BONUS_THRESHOLD:
        return _COMPLETENESS_BONUS, flags

    return 0.0, flags


# ─── VERIFICATION BONUS ───────────────────────────────────────────────────────

def _verification_bonus(signals: dict[str, Any]) -> float:
    """
    Small trust boost when both email and phone are verified.
    A trivially low bar, but it filters out completely bot-generated accounts.
    """
    if signals.get("verified_email", False) and signals.get("verified_phone", False):
        return _VERIFICATION_BONUS
    return 0.0


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def authenticity_score(candidate: dict) -> dict:
    """
    Compute the full authenticity score for a single candidate.

    This is the function called by pipeline.py and rank.py.

    Scoring starts at 100 and adjustments (penalties and bonuses) are applied.
    Final score is clamped to [0, 100].

    Args:
        candidate: Single candidate dict from candidates.jsonl

    Returns:
        {
            "score": float 0-100  — authenticity score
            "flags": list[str]    — list of flag strings for reasoning/UI display
        }
    """
    skills: list[dict] = candidate.get("skills", [])
    career: list[dict] = candidate.get("career_history", [])
    profile: dict[str, Any] = candidate.get("profile", {})
    signals: dict[str, Any] = candidate.get("redrob_signals", {})
    yoe: float = float(profile.get("years_of_experience", 0))
    assessments: dict[str, float] = signals.get("skill_assessment_scores", {})

    # ── HONEYPOT DOUBLE-CHECK (fast-exit, score = 0) ──────────────────────────
    is_honeypot, honeypot_reason = _check_honeypot(skills, career, yoe)
    if is_honeypot:
        return {
            "score": 0.0,
            "flags": [honeypot_reason],  # type: ignore[list-item]
        }

    # ── START AT 100, APPLY ADJUSTMENTS ──────────────────────────────────────
    score: float = 100.0
    all_flags: list[str] = []

    # Skill inflation
    inflation_delta, inflation_flags = _skill_inflation_check(skills, assessments)
    score += inflation_delta
    all_flags.extend(inflation_flags)

    # Suspicious pattern
    suspicious_delta, suspicious_flags = _suspicious_pattern_check(skills, assessments)
    score += suspicious_delta
    all_flags.extend(suspicious_flags)

    # Profile completeness
    completeness_delta, completeness_flags = _completeness_check(signals)
    score += completeness_delta
    all_flags.extend(completeness_flags)

    # Verification bonus
    score += _verification_bonus(signals)

    return {
        "score": round(max(0.0, min(100.0, score)), 4),
        "flags": all_flags,
    }
