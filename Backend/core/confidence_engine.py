"""
core/confidence_engine.py — FHire Confidence Score

WHY THIS FILE EXISTS:
    "How certain are we about this ranking?"

    No AI ranking system is perfect. Thin profiles, missing signals, or
    major disagreement between our four engines all indicate that our
    ranking for that candidate is less certain.

    This feature is a differentiator: most teams will output scores with
    no notion of uncertainty. We surface it explicitly, showing judges that
    our system knows what it doesn't know — a hallmark of production ML.

    THREE FACTORS:
        Evidence Richness (33%):
            Does the candidate have assessments, GitHub, detailed career
            descriptions, and endorsements? More evidence = more confidence.

        Engine Agreement (33%):
            Do all four engines agree? If capability=95 but trajectory=20,
            something contradictory is happening — we should be less sure.
            If all four are closely aligned, we can be confident.

        Profile Completeness (33%):
            profile_completeness_score as a direct proxy for data quality.

    OUTPUT:
        score: 0-100
        label: "High" | "Medium" | "Low"
        explanation: human-readable string for dashboard tooltip

HOW IT CONNECTS:
    Called from pipeline.py and rank.py as:
        conf = confidence_score(candidate, cap, traj, recr, auth)

    cap  → float (capability score 0-100)
    traj → dict  (trajectory dict with "score" key)
    recr → dict  (recruitability dict with "score" key)
    auth → dict  (authenticity dict with "score" key)
"""

from typing import Any


# ─── THRESHOLDS ───────────────────────────────────────────────────────────────

_HIGH_THRESHOLD: float = 0.72   # avg_confidence >= this → "High"
_MEDIUM_THRESHOLD: float = 0.48  # >= this → "Medium", else → "Low"

# Minimum endorsements to be considered "has endorsements"
_ENDORSEMENT_MIN: int = 20

# Minimum description length (characters) to be considered "detailed"
_DESCRIPTION_MIN_LEN: int = 100


# ─── FACTOR 1: EVIDENCE RICHNESS ──────────────────────────────────────────────

def _evidence_richness(candidate: dict) -> float:
    """
    How much verifiable evidence do we have about this candidate?

    Four boolean signals, each worth 0.25:
        has_assessment:      Candidate has taken at least one Redrob skill test.
        has_github:          GitHub activity score is present (not -1 sentinel).
        has_detailed_career: Every career role has a substantial description.
        has_endorsements:    Total endorsements across all skills ≥ 20.

    Returns:
        float 0.0-1.0
    """
    signals: dict[str, Any] = candidate.get("redrob_signals", {})
    career: list[dict] = candidate.get("career_history", [])
    skills: list[dict] = candidate.get("skills", [])

    # Assessment taken?
    has_assessment = len(signals.get("skill_assessment_scores", {})) > 0

    # GitHub linked?
    has_github = signals.get("github_activity_score", -1) != -1

    # Detailed career descriptions?
    has_detailed_career = (
        bool(career)
        and all(len(r.get("description", "")) >= _DESCRIPTION_MIN_LEN for r in career)
    )

    # Has meaningful endorsements?
    total_endorsements = sum(s.get("endorsements", 0) for s in skills)
    has_endorsements = total_endorsements >= _ENDORSEMENT_MIN

    richness = sum([
        has_assessment,
        has_github,
        has_detailed_career,
        has_endorsements,
    ]) / 4.0

    return richness


# ─── FACTOR 2: ENGINE AGREEMENT ───────────────────────────────────────────────

def _engine_agreement(
    cap: float,
    traj: dict,
    recr: dict,
    auth: dict,
) -> float:
    """
    Do all four dimension engines agree on this candidate?

    Method:
        Collect the four dimension scores (0-100 each).
        Compute the range (max - min).
        Large range = disagreement = less confidence.

    If all four engines agree (say all ≈70), range ≈ 0, consistency ≈ 1.0.
    If capability=95 and trajectory=20, range=75, consistency=0.25 — low confidence.

    Returns:
        float 0.0-1.0 (1.0 = full agreement, 0.0 = maximum disagreement)
    """
    traj_score = float(traj.get("score", 50.0)) if isinstance(traj, dict) else float(traj)
    recr_score = float(recr.get("score", 50.0)) if isinstance(recr, dict) else float(recr)
    auth_score = float(auth.get("score", 50.0)) if isinstance(auth, dict) else float(auth)

    all_scores = [
        max(0.0, min(100.0, float(cap))),
        max(0.0, min(100.0, traj_score)),
        max(0.0, min(100.0, recr_score)),
        max(0.0, min(100.0, auth_score)),
    ]

    score_range = max(all_scores) - min(all_scores)
    # Normalise: range of 100 = 0.0, range of 0 = 1.0
    consistency = 1.0 - (score_range / 100.0)
    return max(0.0, consistency)


# ─── FACTOR 3: PROFILE COMPLETENESS ──────────────────────────────────────────

def _profile_completeness_factor(candidate: dict) -> float:
    """
    Direct proxy for data quality — incomplete profiles have missing signals
    that make accurate scoring harder.

    Returns:
        float 0.0-1.0
    """
    signals: dict[str, Any] = candidate.get("redrob_signals", {})
    completeness = float(signals.get("profile_completeness_score", 60.0))
    return max(0.0, min(100.0, completeness)) / 100.0


# ─── LABEL + EXPLANATION BUILDER ─────────────────────────────────────────────

def _build_label_and_explanation(
    avg_conf: float,
    richness: float,
    agreement: float,
    completeness: float,
) -> tuple[str, str]:
    """
    Convert the average confidence value to a human-readable label and explanation.

    Returns:
        (label, explanation)
    """
    if avg_conf >= _HIGH_THRESHOLD:
        label = "High"
        explanation = (
            "Strong evidence base: multiple validated signals, "
            "engines are in agreement, and the profile is well-filled."
        )
    elif avg_conf >= _MEDIUM_THRESHOLD:
        label = "Medium"
        # Surface the weakest factor
        factors = {
            "evidence richness": richness,
            "engine agreement": agreement,
            "profile completeness": completeness,
        }
        weakest = min(factors, key=factors.get)  # type: ignore[arg-type]
        explanation = (
            f"Moderate confidence. Weakest factor: {weakest} "
            f"({factors[weakest] * 100:.0f}/100). "
            "Consider checking the profile manually before outreach."
        )
    else:
        label = "Low"
        explanation = (
            "Sparse signals or significant disagreement between dimension engines. "
            "This ranking may shift with more profile data. "
            "Manual review recommended before outreach."
        )

    return label, explanation


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def confidence_score(
    candidate: dict,
    cap: float,
    traj: dict | float,
    recr: dict | float,
    auth: dict | float,
) -> dict:
    """
    Compute how confident the system is in this candidate's ranking.

    This is the function called by pipeline.py and rank.py.

    Args:
        candidate: Single candidate dict from candidates.jsonl
        cap:       Capability score float 0-100
        traj:      Trajectory dict (must have "score" key) or float
        recr:      Recruitability dict (must have "score" key) or float
        auth:      Authenticity dict (must have "score" key) or float

    Returns:
        {
            "score":       int 0-100    — confidence score
            "label":       str          — "High" | "Medium" | "Low"
            "explanation": str          — human-readable rationale
        }
    """
    richness = _evidence_richness(candidate)
    agreement = _engine_agreement(cap, traj, recr, auth)
    completeness = _profile_completeness_factor(candidate)

    # Equal weighting across all three factors
    avg_conf = (richness + agreement + completeness) / 3.0
    avg_conf = max(0.0, min(1.0, avg_conf))  # defensive clamp

    label, explanation = _build_label_and_explanation(
        avg_conf, richness, agreement, completeness
    )

    return {
        "score": round(avg_conf * 100),
        "label": label,
        "explanation": explanation,
    }
