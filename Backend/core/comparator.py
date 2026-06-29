"""
core/comparator.py — FHire Candidate Comparator

WHY THIS FILE EXISTS:
    Recruiters frequently ask: "You ranked Candidate A above Candidate B — why?"

    This module answers that question dimension by dimension, using the score
    dicts already produced by the pipeline. It NEVER recomputes scores. It only
    reads the dicts passed in and produces a structured comparison.

    Output is consumed by:
        - POST /api/compare  (FastAPI backend → Member 3 frontend)
        - The "Compare" page in the dashboard (side-by-side view)

HOW IT CONNECTS:
    Called from backend/api/routes.py as:
        result = compare_candidates(scores_a, scores_b)

    scores_a / scores_b are the full score dicts returned by pipeline.score_candidate()
    or score_batch(). Required keys in each dict:
        "candidate_id"   → str
        "final_score"    → float 0-1
        "capability"     → float 0-100
        "trajectory"     → dict with "score" key (float 0-100) and "dna" key
        "recruitability" → dict with "score" key (float 0-100)
        "authenticity"   → dict with "score" key (float 0-100)
        "confidence"     → dict with "score" key (int/float 0-100) and "label" key
        "candidate"      → original candidate dict (used for display metadata)

DESIGN NOTES:
    - Differences < 5 points are treated as "roughly equal" (noise level).
    - Differences >= 5 but < 15 are "slight advantage".
    - Differences >= 15 are "clear advantage".
    - final_score comparison uses the 0-1 scale, converted to 0-100 for display.
"""

from typing import Any


# ─── CONSTANTS ────────────────────────────────────────────────────────────────

# Score difference thresholds for characterising advantage magnitude
_NOISE_THRESHOLD: float = 5.0    # below this → "roughly equal"
_SLIGHT_THRESHOLD: float = 15.0  # below this (but >= NOISE) → "slight advantage"
# >= SLIGHT_THRESHOLD → "clear advantage"

# The four scored dimensions compared side by side
_DIMENSIONS: list[tuple[str, str]] = [
    # (display_name, score_key_in_dict)
    ("Capability",     "capability"),
    ("Trajectory",     "trajectory"),
    ("Recruitability", "recruitability"),
    ("Authenticity",   "authenticity"),
    ("Confidence",     "confidence"),
]


# ─── HELPERS ──────────────────────────────────────────────────────────────────

def _extract_score(scores: dict, key: str) -> float:
    """
    Safely extract a numeric score from a score dict entry.
    Handles both plain floats (capability) and nested dicts with a "score" key
    (trajectory, recruitability, authenticity, confidence).
    """
    val = scores.get(key, 0)
    if isinstance(val, dict):
        return float(val.get("score", 0))
    return float(val)


def _advantage_label(diff: float) -> str:
    """
    Convert a raw score difference (A minus B) to a human-readable label
    from A's perspective.
    """
    if diff > _SLIGHT_THRESHOLD:
        return "clear advantage"
    elif diff > _NOISE_THRESHOLD:
        return "slight advantage"
    elif diff < -_SLIGHT_THRESHOLD:
        return "clear disadvantage"
    elif diff < -_NOISE_THRESHOLD:
        return "slight disadvantage"
    else:
        return "roughly equal"


def _extract_profile_meta(scores: dict) -> dict[str, Any]:
    """
    Pull display metadata from the nested candidate dict inside a score dict.
    Returns safe defaults if fields are missing.
    """
    candidate = scores.get("candidate", {})
    profile = candidate.get("profile", {})
    traj = scores.get("trajectory", {})

    return {
        "candidate_id":   scores.get("candidate_id", ""),
        "current_title":  profile.get("current_title", "Unknown"),
        "location":       profile.get("location", "Unknown"),
        "years_of_experience": float(profile.get("years_of_experience", 0)),
        "career_dna":     traj.get("dna", "Unclear") if isinstance(traj, dict) else "Unclear",
        "notice_period":  candidate.get("redrob_signals", {}).get("notice_period_days", None),
        "open_to_work":   candidate.get("redrob_signals", {}).get("open_to_work_flag", False),
        "confidence_label": scores.get("confidence", {}).get("label", "Medium")
                            if isinstance(scores.get("confidence"), dict) else "Medium",
    }


# ─── DIMENSION COMPARISON ─────────────────────────────────────────────────────

def _compare_dimensions(
    scores_a: dict,
    scores_b: dict,
) -> tuple[list[dict], list[str], list[str]]:
    """
    Compare all five dimensions between A and B.

    Returns:
        comparisons:   list of per-dimension comparison dicts
        a_wins:        list of dimension names where A has a meaningful edge
        b_wins:        list of dimension names where B has a meaningful edge
    """
    comparisons: list[dict] = []
    a_wins: list[str] = []
    b_wins: list[str] = []

    for display_name, key in _DIMENSIONS:
        score_a = _extract_score(scores_a, key)
        score_b = _extract_score(scores_b, key)
        diff = score_a - score_b
        label = _advantage_label(diff)

        comparison = {
            "dimension":   display_name,
            "score_a":     round(score_a, 1),
            "score_b":     round(score_b, 1),
            "difference":  round(diff, 1),
            "advantage":   label,
            "winner":      "A" if diff > _NOISE_THRESHOLD
                           else ("B" if diff < -_NOISE_THRESHOLD else "tie"),
        }
        comparisons.append(comparison)

        if diff > _NOISE_THRESHOLD:
            a_wins.append(display_name)
        elif diff < -_NOISE_THRESHOLD:
            b_wins.append(display_name)

    return comparisons, a_wins, b_wins


# ─── VERDICT BUILDER ─────────────────────────────────────────────────────────

def _build_verdict(
    a_wins: list[str],
    b_wins: list[str],
    final_diff_pct: float,
    meta_a: dict,
    meta_b: dict,
) -> str:
    """
    Build a single human-readable verdict sentence that a recruiter can read.
    """
    id_a = meta_a["candidate_id"]
    id_b = meta_b["candidate_id"]

    if not a_wins and not b_wins:
        return (
            f"{id_a} and {id_b} are nearly identical across all dimensions "
            f"(final score gap: {abs(final_diff_pct):.1f} pts). "
            "Ranking reflects minor numerical differences only."
        )

    if a_wins:
        reasons = ", ".join(a_wins)
        verdict = f"{id_a} ranked higher due to stronger {reasons}"
        if b_wins:
            concession = ", ".join(b_wins)
            verdict += f"; {id_b} has an edge in {concession}"
        verdict += f". Final score gap: {final_diff_pct:.1f} pts."
        return verdict

    # B wins everywhere (shouldn't happen if A is ranked above B, but handle it)
    reasons = ", ".join(b_wins)
    return (
        f"{id_b} scores higher on {reasons}, but {id_a} leads on final score "
        f"({final_diff_pct:.1f} pts gap). Recruitability multiplier likely explains the difference."
    )


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def compare_candidates(scores_a: dict, scores_b: dict) -> dict:
    """
    Compare two pre-scored candidates and explain why A ranked above B.

    This function NEVER recomputes any scores. It only reads the dicts
    produced by pipeline.score_candidate() or score_batch().

    Convention: scores_a is the HIGHER-ranked candidate (A > B).
    The caller is responsible for passing them in the correct order.
    If the caller passes them reversed, the verdict will still be accurate
    but will read as "B ranked higher due to…"

    Args:
        scores_a: Full score dict for Candidate A (from pipeline)
        scores_b: Full score dict for Candidate B (from pipeline)

    Returns:
        {
            "candidate_a": {metadata dict},
            "candidate_b": {metadata dict},
            "final_score_a":   float (0-100 scale for readability),
            "final_score_b":   float (0-100 scale for readability),
            "final_score_diff": float (A minus B, 0-100 scale),
            "dimension_comparisons": [
                {
                    "dimension":  str,
                    "score_a":    float 0-100,
                    "score_b":    float 0-100,
                    "difference": float,
                    "advantage":  str,  # "clear advantage" | "slight advantage" | etc.
                    "winner":     str,  # "A" | "B" | "tie"
                },
                ...  # one entry per dimension
            ],
            "dimensions_a_wins": list[str],  # dimension names where A is clearly better
            "dimensions_b_wins": list[str],  # dimension names where B is clearly better
            "verdict":           str,         # human-readable explanation
            "reasoning_a":       str,         # A's grounded reasoning string
            "reasoning_b":       str,         # B's grounded reasoning string
        }
    """
    meta_a = _extract_profile_meta(scores_a)
    meta_b = _extract_profile_meta(scores_b)

    comparisons, a_wins, b_wins = _compare_dimensions(scores_a, scores_b)

    # Convert final_score (0-1) to 0-100 scale for display consistency
    fs_a = float(scores_a.get("final_score", 0)) * 100
    fs_b = float(scores_b.get("final_score", 0)) * 100
    final_diff = round(fs_a - fs_b, 4)

    verdict = _build_verdict(a_wins, b_wins, final_diff, meta_a, meta_b)

    return {
        "candidate_a":          meta_a,
        "candidate_b":          meta_b,
        "final_score_a":        round(fs_a, 4),
        "final_score_b":        round(fs_b, 4),
        "final_score_diff":     final_diff,
        "dimension_comparisons": comparisons,
        "dimensions_a_wins":    a_wins,
        "dimensions_b_wins":    b_wins,
        "verdict":              verdict,
        "reasoning_a":          scores_a.get("reasoning", ""),
        "reasoning_b":          scores_b.get("reasoning", ""),
    }
