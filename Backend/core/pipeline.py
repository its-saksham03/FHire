"""
core/pipeline.py — FHire Main Scoring Pipeline

WHY THIS FILE EXISTS:
  This is the "assembler" — it takes all the individual engine scores and
  combines them into the final score using the master formula.

  Member 2's modules (recruitability, authenticity, confidence, reasoning,
  counterfactual) plug in HERE. This file defines the clean interface between
  Member 1's engines and Member 2's engines.

  The pipeline exposes two functions:
    1. score_candidate()   → scores a single candidate (used by rank.py)
    2. score_batch()       → scores multiple candidates (used by FastAPI backend)

MASTER FORMULA:
  base_score = (
      capability    × 0.40
    + trajectory    × 0.25
    + recruitability × 0.25
    + authenticity  × 0.10
  ) / 100

  final_score = base_score × recruitability_multiplier

  WHY MULTIPLICATIVE RECRUITABILITY:
  If someone hasn't logged in for 6 months and has 5% response rate, they are
  NOT available. Adding recruitability as additive means inactive candidates can
  still score in the top 5 just from capability alone. Making it a multiplier
  means: multiplier = 0.1 → score drops by 90% regardless of capability.
  The JD explicitly asked for this behavior.

HOW MEMBER 2 PLUGS IN:
  Member 2 creates:
    - core/recruitability_engine.py  → function: recruitability_score_and_multiplier()
    - core/authenticity_engine.py    → function: authenticity_score()
    - core/confidence_engine.py      → function: confidence_score()
    - core/reasoning_generator.py    → function: generate_reasoning()
    - core/counterfactual.py         → function: what_would_it_take()

  This pipeline.py already has the import structure ready.
  Member 2 just needs to implement those functions with the right signatures.

FALLBACKS:
  If Member 2's modules aren't ready yet, we have stub fallbacks so rank.py
  still runs and produces valid output. This way Member 1 can test independently.
"""

import importlib
from datetime import date, datetime

from core.capability_engine import capability_score
from core.trajectory_engine import trajectory_score_final

# Try to import Member 2's modules — fallback to stubs if not ready yet
# This lets Member 1 test independently before Member 2 is done

def _load_m2_module(module_path: str, function_name: str):
    """Dynamically load Member 2's functions, with graceful fallback."""
    try:
        mod = importlib.import_module(module_path)
        return getattr(mod, function_name)
    except (ImportError, AttributeError):
        return None


# Attempt to load Member 2's engines
_recruitability_fn = _load_m2_module("core.recruitability_engine", "recruitability_score_and_multiplier")
_authenticity_fn   = _load_m2_module("core.authenticity_engine",   "authenticity_score")
_confidence_fn     = _load_m2_module("core.confidence_engine",     "confidence_score")
_reasoning_fn      = _load_m2_module("core.reasoning_generator",   "generate_reasoning")
_counterfactual_fn = _load_m2_module("core.counterfactual",        "what_would_it_take")


# ─── STUB FALLBACKS (used until Member 2's modules are ready) ─────────────────

TODAY = date(2026, 6, 25)   # Hackathon date — used for recency calculations


def _stub_recruitability(candidate: dict, signal_distributions: dict) -> dict:
    """
    Stub recruitability engine — basic logic until Member 2 builds the full version.
    Uses key signals: open_to_work, last_active_date, response_rate, notice_period.
    """
    signals = candidate.get("redrob_signals", {})
    profile = candidate.get("profile", {})

    score = 0.0

    # Open to work
    if signals.get("open_to_work_flag", False):
        score += 20

    # Activity recency
    try:
        last_active_str = signals.get("last_active_date", "2020-01-01")
        last_active = datetime.strptime(last_active_str, "%Y-%m-%d").date()
        days_inactive = (TODAY - last_active).days

        if days_inactive <= 7:
            score += 30
        elif days_inactive <= 30:
            score += 22
        elif days_inactive <= 90:
            score += 12
        elif days_inactive <= 180:
            score += 4
        # 6+ months = 0
    except (ValueError, TypeError):
        score += 10  # Unknown → neutral

    # Response rate (simple percentile-ish approximation)
    rr = signals.get("recruiter_response_rate", 0.3)
    score += rr * 25  # Max ~25 points

    # Notice period (lower = better)
    notice = signals.get("notice_period_days", 60)
    if notice <= 15:
        score += 15
    elif notice <= 30:
        score += 12
    elif notice <= 60:
        score += 6
    elif notice <= 90:
        score += 3
    # 90+ = 0 extra

    # Location (India preferred)
    country = profile.get("country", "")
    loc = profile.get("location", "").lower()
    if country == "India":
        if any(p in loc for p in ["pune", "noida"]):
            score += 10
        elif any(p in loc for p in ["hyderabad", "mumbai", "delhi", "bangalore", "bengaluru", "gurgaon"]):
            score += 7
        else:
            score += 3

    score = min(100.0, score)

    # Multiplier: 0.1 to 1.0
    multiplier = 0.1 + (score / 100.0) * 0.9

    return {
        "score": score,
        "multiplier": multiplier,
        "breakdown": {
            "availability": min(50, score * 0.5),
            "responsiveness": min(35, score * 0.35),
            "logistics": min(25, score * 0.25),
        },
        "_stub": True  # Flag so Member 2 knows this is the stub
    }


def _stub_authenticity(candidate: dict) -> dict:
    """Stub authenticity engine."""
    skills = candidate.get("skills", [])
    signals = candidate.get("redrob_signals", {})
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    assessments = signals.get("skill_assessment_scores", {})

    score = 85.0
    flags = []

    # Honeypot checks (duplicate with disqualifier but safety net)
    zero_experts = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 1) == 0
    )
    if zero_experts >= 3:
        return {"score": 0, "flags": ["HONEYPOT: expert skills, 0 months"], "_stub": True}

    for role in candidate.get("career_history", []):
        if role.get("duration_months", 0) > (yoe * 12) + 18:
            return {"score": 0, "flags": ["HONEYPOT: impossible career duration"], "_stub": True}

    # Skill inflation check
    for skill in skills:
        name = skill.get("name", "")
        if name in assessments:
            ass = assessments[name]
            claimed = skill.get("proficiency", "")
            if claimed == "expert" and ass < 50:
                score -= 15
                flags.append(f"skill_inflation: {name} — claimed expert, scored {ass:.0f}/100")
            elif claimed == "advanced" and ass < 30:
                score -= 8
                flags.append(f"skill_inflation: {name} — claimed advanced, scored {ass:.0f}/100")
            elif ass >= 80:
                score += 3

    # Profile completeness
    completeness = signals.get("profile_completeness_score", 60)
    if completeness < 50:
        score -= 10
        flags.append("incomplete profile")
    elif completeness >= 85:
        score += 5

    # Verification bonus
    if signals.get("verified_email") and signals.get("verified_phone"):
        score += 5

    return {
        "score": max(0.0, min(100.0, score)),
        "flags": flags,
        "_stub": True
    }


def _stub_confidence(candidate: dict, cap: float, traj: dict, recr: dict, auth: dict) -> dict:
    """Stub confidence engine."""
    signals = candidate.get("redrob_signals", {})
    career = candidate.get("career_history", [])

    factors = []

    # Evidence richness
    has_assessment = len(signals.get("skill_assessment_scores", {})) > 0
    has_github = signals.get("github_activity_score", -1) != -1
    has_detailed_career = all(len(r.get("description", "")) > 80 for r in career) if career else False
    total_endors = sum(s.get("endorsements", 0) for s in candidate.get("skills", []))
    has_endorsements = total_endors > 20

    evidence_richness = sum([has_assessment, has_github, has_detailed_career, has_endorsements]) / 4.0
    factors.append(evidence_richness)

    # Engine agreement
    all_scores = [cap, traj["score"], recr["score"], auth["score"]]
    score_range = max(all_scores) - min(all_scores)
    consistency = 1.0 - (score_range / 100.0)
    factors.append(max(0.0, consistency))

    # Profile completeness
    factors.append(signals.get("profile_completeness_score", 60) / 100.0)

    avg_conf = sum(factors) / len(factors)

    if avg_conf >= 0.72:
        label = "High"
    elif avg_conf >= 0.48:
        label = "Medium"
    else:
        label = "Low"

    return {"score": round(avg_conf * 100), "label": label, "_stub": True}


def _stub_reasoning(candidate: dict, scores: dict, rank: int) -> str:
    """Stub reasoning generator — produces specific (not template) text."""
    profile = candidate.get("profile", {})
    signals = candidate.get("redrob_signals", {})
    career = candidate.get("career_history", [])

    parts = []

    # Opening: title + experience
    parts.append(f"{profile.get('current_title', 'Engineer')} with {profile.get('years_of_experience', 0):.1f}yrs")

    # Career DNA
    dna = scores.get("trajectory", {}).get("dna", "Unclear")
    if dna in ("Startup Builder", "Scale Expert", "Product Engineer"):
        parts.append(f"career DNA: {dna}")
    elif dna == "Research Specialist":
        parts.append("caution: research-only background, no production deployment")

    # Best evidence sentence from career
    EVIDENCE_KW = [
        "rag", "retrieval", "ranking", "embedding", "vector",
        "faiss", "ndcg", "production", "deployed", "queries per",
        "learning to rank", "fine-tun", "hybrid", "bm25",
        "million", "at scale", "serving"
    ]
    best_sentence = None
    best_company = None

    for role in sorted(career, key=lambda r: r.get("start_date", ""), reverse=True):
        for sent in role.get("description", "").split(". "):
            found = sum(1 for kw in EVIDENCE_KW if kw in sent.lower())
            if found >= 2:
                best_sentence = sent.strip()[:140]
                best_company = role.get("company", "")
                break
        if best_sentence:
            break

    if best_sentence and best_company:
        parts.append(f"at {best_company}: {best_sentence}")
    else:
        parts.append("limited production ML evidence in career descriptions")

    # Trajectory insight
    direction = scores.get("trajectory", {}).get("direction", 50)
    is_hopper = scores.get("trajectory", {}).get("is_job_hopper", False)
    avg_tenure = scores.get("trajectory", {}).get("tenure_avg_months", 24)

    if direction >= 80:
        parts.append("trajectory strongly pointing toward AI engineering")
    if is_hopper:
        parts.append(f"job-hopping concern: avg {avg_tenure:.0f}mo/role")

    # Availability signals
    notice = signals.get("notice_period_days", 60)
    open_w = signals.get("open_to_work_flag", False)
    rr = signals.get("recruiter_response_rate", 0.3)

    avail = []
    if open_w:
        avail.append("actively looking")
    else:
        avail.append("not open to work")

    if notice <= 30:
        avail.append(f"{notice}d notice")
    elif notice > 60:
        avail.append(f"long notice ({notice}d)")

    if rr >= 0.70:
        avail.append(f"responsive ({rr:.0%} response rate)")
    elif rr < 0.15:
        avail.append(f"low response rate ({rr:.0%}) — concern")

    parts.append("; ".join(avail))

    # GitHub
    gh = signals.get("github_activity_score", -1)
    if gh >= 60:
        parts.append(f"active GitHub ({gh:.0f}/100)")
    elif gh == -1:
        parts.append("no public GitHub")

    # Confidence caveat
    conf_label = scores.get("confidence", {}).get("label", "Medium")
    if conf_label == "Low":
        parts.append("confidence: Low — sparse evidence, signals limited")

    # Auth flags
    flags = scores.get("authenticity", {}).get("flags", [])
    if flags:
        parts.append(f"caution: {flags[0]}")

    return "; ".join(parts) + "."


# ─── MAIN SCORE FUNCTION ──────────────────────────────────────────────────────

def score_candidate(
    candidate: dict,
    semantic_score: float,
    signal_distributions: dict,
    all_final_scores: list | None = None,
    current_rank: int | None = None,
) -> dict:
    """
    Score a single candidate across all 4 dimensions and compute final score.

    Args:
        candidate:            candidate dict from candidates.jsonl
        semantic_score:       pre-computed cosine similarity score 0-100
        signal_distributions: pre-loaded distributions dict for percentile math
        all_final_scores:     list of all final scores (for counterfactual rank estimation)
        current_rank:         this candidate's rank (for counterfactual)

    Returns:
        Full score dict:
        {
          "candidate_id": str,
          "final_score": float 0-1,
          "capability": float 0-100,
          "trajectory": dict (score + breakdown),
          "recruitability": dict (score + multiplier + breakdown),
          "authenticity": dict (score + flags),
          "confidence": dict (score + label),
          "reasoning": str,
          "counterfactual": dict | None,
          "candidate": dict (original)
        }
    """
    # ── DIMENSION 1: CAPABILITY ────────────────────────────────────────────────
    cap = capability_score(candidate, semantic_score)

    # ── DIMENSION 2: TRAJECTORY ────────────────────────────────────────────────
    traj = trajectory_score_final(candidate)

    # ── DIMENSION 3: RECRUITABILITY ────────────────────────────────────────────
    # Use Member 2's engine if available, else fall back to stub
    recr_fn = _recruitability_fn or _stub_recruitability
    recr = recr_fn(candidate, signal_distributions)

    # ── DIMENSION 4: AUTHENTICITY ──────────────────────────────────────────────
    auth_fn = _authenticity_fn or _stub_authenticity
    auth = auth_fn(candidate)

    # ── BASE SCORE ─────────────────────────────────────────────────────────────
    base = (
        cap                * 0.40
        + traj["score"]    * 0.25
        + recr["score"]    * 0.25
        + auth["score"]    * 0.10
    ) / 100.0

    # ── FINAL SCORE: base × recruitability multiplier ──────────────────────────
    final_score = base * recr["multiplier"]

    # ── CONFIDENCE ─────────────────────────────────────────────────────────────
    conf_fn = _confidence_fn or _stub_confidence
    conf = conf_fn(candidate, cap, traj, recr, auth)

    result = {
        "candidate_id": candidate.get("candidate_id", ""),
        "final_score": final_score,
        "capability": cap,
        "trajectory": traj,
        "recruitability": recr,
        "authenticity": auth,
        "confidence": conf,
        "candidate": candidate,
        # Store multiplier for counterfactual
        "_recruitability_multiplier": recr["multiplier"],
    }

    # ── REASONING ─────────────────────────────────────────────────────────────
    # (only when rank is known — called post-sort in rank.py)
    reasoning_fn = _reasoning_fn or _stub_reasoning
    result["reasoning"] = reasoning_fn(candidate, result, current_rank or 0)

    # ── COUNTERFACTUAL ─────────────────────────────────────────────────────────
    if all_final_scores is not None and current_rank is not None:
        cf_fn = _counterfactual_fn or None
        if cf_fn:
            result["counterfactual"] = cf_fn(
                candidate, final_score, current_rank,
                all_final_scores, signal_distributions
            )
        else:
            result["counterfactual"] = None
    else:
        result["counterfactual"] = None

    return result


def score_batch(
    candidates: list,
    semantic_scores,  # numpy array
    signal_distributions: dict,
    include_counterfactual: bool = False,
) -> list:
    """
    Score a batch of candidates. Used by FastAPI backend.

    Args:
        candidates:           list of candidate dicts
        semantic_scores:      numpy array of semantic scores (same order as candidates)
        signal_distributions: pre-loaded distributions dict
        include_counterfactual: whether to compute counterfactual (slow)

    Returns:
        List of score dicts, sorted by final_score descending.
    """
    import numpy as np

    results = []
    for i, candidate in enumerate(candidates):
        sem_score = float(semantic_scores[i]) * 100 if i < len(semantic_scores) else 50.0
        result = score_candidate(candidate, sem_score, signal_distributions)
        results.append(result)

    # Sort by final score descending
    results.sort(key=lambda x: (-x["final_score"], x["candidate_id"]))

    # Add ranks
    all_scores = [r["final_score"] for r in results]
    for i, r in enumerate(results):
        r["rank"] = i + 1
        if include_counterfactual:
            cf_fn = _counterfactual_fn or None
            if cf_fn:
                r["counterfactual"] = cf_fn(
                    r["candidate"], r["final_score"], r["rank"],
                    all_scores, signal_distributions
                )

    return results
