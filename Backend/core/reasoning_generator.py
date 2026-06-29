"""
core/reasoning_generator.py — FHire Grounded Reasoning Generator

WHY THIS FILE EXISTS:
    Judges manually check 10 random reasoning rows.
    Template responses are penalised. Specific, grounded responses are rewarded.

    The goal: produce reasoning that reads like a senior recruiter wrote it —
    referencing actual companies, actual descriptions, actual numbers —
    not generic AI filler like "Strong candidate with relevant experience."

RULES (strictly enforced):
    1. Every claim must come from the candidate's own data.
    2. No hallucination — do NOT invent skills, companies, or metrics.
    3. No generic templates — every sentence is assembled from real fields.
    4. Use actual numbers: years of experience, notice period, response rate.
    5. Mention Career DNA, trajectory direction, and concerns honestly.
    6. If Confidence is Low, say so.
    7. If there are authenticity flags, surface the most important one.

FORMAT:
    Semicolon-separated sentence fragments, ending with a period.
    Mirrors the format used by the master plan and stub reasoning:
        "Title with X.Xyrs; career DNA: Y; at CompanyZ: <actual sentence>;
        trajectory insight; availability signals; GitHub if notable; concerns."

HOW IT CONNECTS:
    Called from pipeline.py and rank.py as:
        reasoning = generate_reasoning(candidate, scores, rank)

    scores dict (assembled by rank.py/pipeline.py) contains:
        scores["capability"]          → float
        scores["trajectory"]          → dict with keys: score, dna, direction,
                                          is_job_hopper, tenure_avg_months
        scores["recruitability"]      → dict with keys: score, multiplier, breakdown
        scores["authenticity"]        → dict with keys: score, flags
        scores["confidence"]          → dict with keys: score, label
        scores["final_score"]         → float

    rank → int (1-based position in final ranking)
"""

from typing import Any


# ─── EVIDENCE KEYWORDS ────────────────────────────────────────────────────────
# Used to find the BEST sentence from career descriptions — one that shows
# actual production work rather than a generic project description.

_EVIDENCE_KEYWORDS: list[str] = [
    "rag", "retrieval", "ranking", "embedding", "vector",
    "faiss", "ndcg", "production", "deployed", "queries per",
    "learning to rank", "fine-tun", "hybrid", "bm25",
    "million", "at scale", "serving", "inference", "qps",
    "latency", "opensearch", "elasticsearch", "pinecone", "weaviate",
    "qdrant", "milvus", "semantic search", "reranking", "lora",
]

# Minimum keyword hits in a single sentence to qualify as "strong evidence"
_EVIDENCE_MIN_HITS: int = 2

# Maximum characters to include from a single evidence sentence (avoid very long text)
_EVIDENCE_MAX_CHARS: int = 140


# ─── HELPER: FIND BEST EVIDENCE SENTENCE ─────────────────────────────────────

def _find_best_evidence_sentence(
    career: list[dict],
) -> tuple[str | None, str | None]:
    """
    Scan all career descriptions (most recent role first) and return the single
    sentence with the most evidence keyword hits.

    Returns:
        (sentence_text, company_name) or (None, None) if nothing found
    """
    best_sentence: str | None = None
    best_company: str | None = None
    best_hits: int = 0

    # Most recent role first — recency matters for relevance
    for role in sorted(career, key=lambda r: r.get("start_date", ""), reverse=True):
        description = role.get("description", "")
        company = role.get("company", "")

        for raw_sent in description.split(". "):
            sent_lower = raw_sent.lower()
            hits = sum(1 for kw in _EVIDENCE_KEYWORDS if kw in sent_lower)

            if hits >= _EVIDENCE_MIN_HITS and hits > best_hits:
                best_hits = hits
                best_sentence = raw_sent.strip()[:_EVIDENCE_MAX_CHARS]
                best_company = company
                # Don't break — keep looking for an even better sentence

    return best_sentence, best_company


# ─── HELPER: BUILD AVAILABILITY FRAGMENT ─────────────────────────────────────

def _build_availability_fragment(signals: dict[str, Any]) -> str:
    """
    Build a concise availability fragment from real signal values.

    Example outputs:
        "actively looking; 15d notice; responsive (82% response rate)"
        "not open to work; long notice (90d); low response rate (8%)"
    """
    parts: list[str] = []

    open_w: bool = signals.get("open_to_work_flag", False)
    notice: int = int(signals.get("notice_period_days", 60))
    rr: float = float(signals.get("recruiter_response_rate", 0.3))

    # Open-to-work status
    parts.append("actively looking" if open_w else "not open to work")

    # Notice period — only mention if notable
    if notice <= 15:
        parts.append(f"immediate joiner ({notice}d notice)")
    elif notice <= 30:
        parts.append(f"{notice}d notice")
    elif notice > 60:
        parts.append(f"long notice ({notice}d)")
    # 31–60 days: skip, unremarkable

    # Response rate — only mention if clearly good or clearly bad
    if rr >= 0.70:
        parts.append(f"responsive ({rr:.0%} response rate)")
    elif rr < 0.15:
        parts.append(f"low response rate ({rr:.0%}) — concern")

    return "; ".join(parts)


# ─── HELPER: BUILD TRAJECTORY FRAGMENT ───────────────────────────────────────

def _build_trajectory_fragment(traj: dict) -> str | None:
    """
    Build a short trajectory insight fragment from the trajectory dict.
    Returns None if there is nothing interesting to say.
    """
    direction: float = float(traj.get("direction", 50.0))
    is_hopper: bool = traj.get("is_job_hopper", False)
    avg_tenure: float = float(traj.get("tenure_avg_months", 24.0))
    velocity: float = float(traj.get("velocity", 50.0))

    parts: list[str] = []

    if direction >= 85:
        parts.append("trajectory strongly pointing toward AI engineering")
    elif direction >= 70:
        parts.append("positive career trajectory toward AI/ML roles")
    elif direction <= 30:
        parts.append("trajectory moving away from AI engineering")

    if is_hopper:
        parts.append(f"job-hopping concern (avg {avg_tenure:.0f}mo/role)")
    elif avg_tenure >= 36 and velocity >= 70:
        parts.append("stable tenure with fast progression")

    return "; ".join(parts) if parts else None


# ─── HELPER: BUILD GITHUB FRAGMENT ───────────────────────────────────────────

def _build_github_fragment(signals: dict[str, Any]) -> str | None:
    """
    Return a GitHub fragment only when it is interesting (high or absent).
    Mediocre GitHub scores are not worth mentioning.
    """
    gh = signals.get("github_activity_score", -1)
    if gh == -1 or gh is None:
        return "no public GitHub"
    gh = float(gh)
    if gh >= 75:
        return f"active GitHub ({gh:.0f}/100)"
    if gh >= 50:
        return f"GitHub score: {gh:.0f}/100"
    # Below 50 — not worth highlighting
    return None


# ─── PUBLIC API ───────────────────────────────────────────────────────────────

def generate_reasoning(candidate: dict, scores: dict, rank: int) -> str:
    """
    Generate a grounded, recruiter-style reasoning string for this candidate.

    Every sentence fragment is sourced directly from candidate data.
    No hallucinations. No generic templates.

    Args:
        candidate: Single candidate dict from candidates.jsonl
        scores:    Full scores dict assembled by pipeline.py / rank.py
                   (contains capability, trajectory, recruitability,
                    authenticity, confidence, final_score)
        rank:      1-based rank of this candidate in the final output

    Returns:
        str: semicolon-separated reasoning, ending with "."
    """
    profile: dict[str, Any] = candidate.get("profile", {})
    signals: dict[str, Any] = candidate.get("redrob_signals", {})
    career: list[dict] = candidate.get("career_history", [])

    traj: dict = scores.get("trajectory", {})
    auth: dict = scores.get("authenticity", {})
    conf: dict = scores.get("confidence", {})

    parts: list[str] = []

    # ── 1. Opening: title + years of experience ───────────────────────────────
    title: str = profile.get("current_title", "Engineer")
    yoe: float = float(profile.get("years_of_experience", 0))
    parts.append(f"{title} with {yoe:.1f}yrs experience")

    # ── 2. Career DNA ─────────────────────────────────────────────────────────
    dna: str = traj.get("dna", "Unclear")
    if dna in ("Startup Builder", "Scale Expert", "Product Engineer"):
        parts.append(f"career DNA: {dna}")
    elif dna == "Research Specialist":
        parts.append("caution: research-only background (JD requires production deployment)")
    elif dna == "Consulting Only":
        parts.append("caution: consulting-only background (JD prefers product experience)")
    # "Unclear" — skip, nothing useful to say

    # ── 3. Best production evidence sentence ──────────────────────────────────
    best_sent, best_co = _find_best_evidence_sentence(career)
    if best_sent and best_co:
        parts.append(f"at {best_co}: {best_sent}")
    else:
        parts.append("limited production ML evidence found in career descriptions")

    # ── 4. Trajectory insight ─────────────────────────────────────────────────
    traj_fragment = _build_trajectory_fragment(traj)
    if traj_fragment:
        parts.append(traj_fragment)

    # ── 5. Availability signals ───────────────────────────────────────────────
    avail_fragment = _build_availability_fragment(signals)
    if avail_fragment:
        parts.append(avail_fragment)

    # ── 6. GitHub ─────────────────────────────────────────────────────────────
    github_fragment = _build_github_fragment(signals)
    if github_fragment:
        parts.append(github_fragment)

    # ── 7. Confidence caveat (only for Low confidence) ────────────────────────
    conf_label: str = conf.get("label", "Medium")
    if conf_label == "Low":
        parts.append(
            "confidence: Low — sparse evidence or engine disagreement; "
            "manual review recommended"
        )

    # ── 8. Most important authenticity flag (if any) ──────────────────────────
    flags: list[str] = auth.get("flags", [])
    if flags:
        # Show only the first flag to avoid cluttering the reasoning text
        parts.append(f"caution: {flags[0]}")

    return "; ".join(parts) + "."
