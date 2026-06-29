"""
core/capability_engine.py — FHire Capability Score (Dimension 1, 40%)

WHY THIS FILE EXISTS:
  "Can this person actually do this job?"

  Most teams will just look at the skills list and count AI keywords.
  That's the TRAP the organizers built. Someone can put "RAG, Embeddings,
  Vector DB" in their skills section and never have used any of them.

  We do THREE things instead:
    1. Career Evidence Mining: Read what they ACTUALLY DID in their job
       descriptions. "Built production RAG serving 20M queries" >> "Know RAG"
    2. Skill Trust Score: Weight skills by proficiency, endorsements, duration,
       AND assessment scores. If you claimed Expert but scored 42/100 → penalty.
    3. Semantic Similarity: Pre-computed cosine similarity between candidate
       text and the job description (via bge-small embeddings).

  Final capability_score = weighted combination of all three.

HOW IT CONNECTS:
  - Gets pre-computed semantic_score from rank.py (loaded from embeddings.npz)
  - Processes candidate dict from candidates.jsonl
  - Returns a single score 0-100
"""

# ─── PRODUCTION EVIDENCE KEYWORDS ─────────────────────────────────────────────
# These are keywords found in career DESCRIPTIONS that indicate real production work.
# Point values indicate how rare/valuable each signal is.
# Higher points = rarer, more valuable evidence of relevant work.

PRODUCTION_EVIDENCE = {
    # Core retrieval/ranking systems (most important for this JD)
    "rag": 5,
    "retrieval augmented": 5,
    "hybrid retrieval": 5,
    "learning to rank": 5,
    "ltr": 4,
    "bm25": 4,
    "ndcg": 5,
    "mrr": 4,
    "map@": 4,
    "evaluation framework": 4,
    "a/b test": 4,
    "offline eval": 4,
    "online eval": 4,

    # Vector databases (strong signal — hands-on infra)
    "faiss": 4,
    "pinecone": 4,
    "weaviate": 4,
    "qdrant": 4,
    "milvus": 4,
    "chroma": 3,
    "pgvector": 3,

    # Search infrastructure
    "elasticsearch": 3,
    "opensearch": 3,
    "solr": 2,

    # Core ML signals
    "ranking": 4,
    "retrieval": 4,
    "recommendation": 4,
    "embedding": 4,
    "vector": 3,
    "semantic search": 4,
    "dense retrieval": 4,
    "sparse retrieval": 3,
    "reranking": 4,
    "cross-encoder": 4,

    # Production signals (actual deployment = rare)
    "deployed": 3,
    "production": 3,
    "real users": 4,
    "queries per": 4,
    "at scale": 3,
    "serving": 3,
    "latency": 3,
    "inference": 3,
    "throughput": 3,

    # Fine-tuning signals
    "fine-tun": 3,
    "lora": 3,
    "qlora": 3,
    "peft": 3,
    "rlhf": 3,

    # Models (specific knowledge)
    "sentence transformer": 4,
    "bge": 4,
    "e5": 3,
    "openai ada": 3,
    "instructor": 3,

    # Weak positive signals (somewhat relevant)
    "xgboost": 2,
    "lightgbm": 2,
    "nlp": 2,
    "language model": 2,
    "transformer": 2,
    "bert": 2,
}

# Scale signals — when these appear TOGETHER with evidence keywords,
# it means they didn't just do a toy project — they did it at scale
SCALE_SIGNALS = [
    "million", "billion", "queries", "users", "production",
    "deployed", "serving", "scale", "latency", "throughput",
    "real-time", "requests per", "qps"
]

# ─── MUST-HAVE SKILLS ─────────────────────────────────────────────────────────
# Skills that directly matter for this JD. Point values = relevance weight.
MUST_HAVE_SKILLS = {
    "embeddings": 10,
    "sentence transformers": 10,
    "bge": 8,
    "e5": 8,
    "vector database": 10,
    "faiss": 8,
    "pinecone": 8,
    "weaviate": 8,
    "qdrant": 8,
    "milvus": 8,
    "chroma": 7,
    "elasticsearch": 7,
    "opensearch": 7,
    "python": 8,
    "ranking": 9,
    "retrieval": 9,
    "search": 7,
    "ndcg": 8,
    "evaluation": 7,
    "nlp": 7,
    "hybrid search": 9,
    "bm25": 8,
    "rag": 9,
    "information retrieval": 9,
    "reranking": 8,
    "dense retrieval": 8,
    "semantic search": 9,
    "llm": 7,
    "langchain": 6,
    "llamaindex": 7,
}

# Nice-to-have skills (secondary relevance)
GOOD_TO_HAVE_SKILLS = {
    "lora": 5,
    "qlora": 5,
    "peft": 5,
    "fine-tuning": 5,
    "learning to rank": 6,
    "xgboost": 4,
    "lightgbm": 4,
    "distributed systems": 4,
    "kafka": 3,
    "spark": 3,
    "open source": 4,
    "pytorch": 5,
    "tensorflow": 4,
    "hugging face": 6,
    "transformers": 6,
}

# Skills that actively hurt the score (wrong domain)
NEGATIVE_SKILLS = {
    "computer vision": -3,
    "image classification": -2,
    "object detection": -2,
    "speech recognition": -3,
    "tts": -3,
    "asr": -3,
    "photoshop": -2,
    "figma": -2,
    "graphic design": -2,
    "excel": -1,
    "tableau": -1,
}


# ─── COMPONENT 1: CAREER EVIDENCE SCORE ──────────────────────────────────────

def career_evidence_score(candidate: dict) -> float:
    """
    Reads career history DESCRIPTIONS (not skills, not title) and looks for
    evidence of real production ML/IR work.

    Key insight: "Built production RAG serving 20M queries" >>>>> "Know RAG"
    Both contain "RAG" but one is evidence of real work, one is just a keyword.

    We detect "strong evidence" via the Evidence Strength Multiplier:
    - If a sentence contains 2+ evidence keywords AND 2+ scale signals → 1.5x bonus
    - This separates "I know RAG" from "deployed RAG at 20M queries/day"

    Returns:
        float 0-50 (this component contributes max 50 points)
    """
    career = candidate.get("career_history", [])
    all_descriptions = " ".join(r.get("description", "").lower() for r in career)

    # Count raw evidence points
    raw_points = 0
    for keyword, points in PRODUCTION_EVIDENCE.items():
        if keyword in all_descriptions:
            raw_points += points

    # Evidence Strength Multiplier — sentence-level analysis
    # Splits on ". " to get individual sentences, checks co-occurrence
    best_strength = 1.0
    sentences = all_descriptions.split(". ")

    for sentence in sentences:
        scale_count = sum(1 for s in SCALE_SIGNALS if s in sentence)
        evidence_count = sum(1 for kw in PRODUCTION_EVIDENCE if kw in sentence)

        if evidence_count >= 2 and scale_count >= 2:
            best_strength = 1.5   # Strong production evidence — 50% bonus
            break
        elif evidence_count >= 2 and scale_count >= 1:
            best_strength = max(best_strength, 1.3)   # Good evidence
        elif evidence_count >= 3:
            best_strength = max(best_strength, 1.1)   # Multiple mentions, some credibility

    score = min(raw_points * best_strength, 50.0)
    return score


# ─── COMPONENT 2: SKILL TRUST SCORE ──────────────────────────────────────────

def skill_trust_score(candidate: dict) -> float:
    """
    Evaluates the TRUSTWORTHINESS of skills, not just their presence.

    For each skill:
    - Base trust: proficiency level (expert=1.0, advanced=0.75, etc.)
    - Endorsement boost: up to +0.3 if many people endorsed this skill
    - Duration boost: up to +0.3 if used for 3+ years
    - Assessment factor: if they took Redrob's skill test, validate their claim
        → Expert claimed but scored <50/100 → heavy penalty (0.4x)
        → Expert claimed, scored 80+ → bonus (1.2x) — trust multiplied

    Anti-keyword-stuffing: Someone can't just add "RAG" as Expert if they
    have 0 endorsements, 1 month usage, and failed the assessment.

    Returns:
        float 0-100
    """
    proficiency_weights = {
        "expert": 1.0,
        "advanced": 0.75,
        "intermediate": 0.5,
        "beginner": 0.25,
    }

    skills = candidate.get("skills", [])
    assessments = candidate.get("redrob_signals", {}).get("skill_assessment_scores", {})

    total_weighted = 0.0
    max_possible = 0.0

    for skill in skills:
        name_lower = skill.get("name", "").lower()

        # Check negative skills first
        neg_total = sum(v for k, v in NEGATIVE_SKILLS.items() if k in name_lower)
        if neg_total < 0:
            total_weighted += neg_total * 5  # Penalize (small impact on 0-100 scale)
            continue

        # Find relevance value for this skill
        relevance = 0.0
        for must_skill, value in MUST_HAVE_SKILLS.items():
            if must_skill in name_lower or name_lower in must_skill:
                relevance = float(value)
                break

        if relevance == 0:
            for good_skill, value in GOOD_TO_HAVE_SKILLS.items():
                if good_skill in name_lower or name_lower in good_skill:
                    relevance = float(value) * 0.5
                    break

        if relevance == 0:
            continue  # Skill not relevant to this JD → skip

        # Trust components
        base_trust = proficiency_weights.get(skill.get("proficiency", "beginner"), 0.25)

        # Endorsement boost: 30 endorsements → full boost
        endorsement_boost = min(skill.get("endorsements", 0) / 30.0, 1.0) * 0.3

        # Duration boost: 36 months (3 years) → full boost
        duration_boost = min(skill.get("duration_months", 0) / 36.0, 1.0) * 0.3

        # Assessment validation factor
        assessment_factor = 1.0
        skill_name_orig = skill.get("name", "")
        if skill_name_orig in assessments:
            ass_score = assessments[skill_name_orig]
            claimed = skill.get("proficiency", "")

            if claimed == "expert" and ass_score < 50:
                assessment_factor = 0.4   # Heavy penalty: claimed expert, failed test
            elif claimed == "advanced" and ass_score < 35:
                assessment_factor = 0.6   # Moderate penalty
            elif claimed == "intermediate" and ass_score < 20:
                assessment_factor = 0.7   # Mild penalty
            elif ass_score >= 80:
                assessment_factor = 1.2   # Bonus: validated skill

        skill_trust = (base_trust + endorsement_boost + duration_boost) * assessment_factor
        total_weighted += relevance * skill_trust
        max_possible += relevance

    if max_possible == 0:
        return 0.0

    return max(0.0, min(100.0, (total_weighted / max_possible) * 100.0))


# ─── MAIN CAPABILITY SCORE ────────────────────────────────────────────────────

def capability_score(candidate: dict, semantic_score: float) -> float:
    """
    Final Capability Score — combines all three components.

    Component weights:
    - Career Evidence:   40 pts max (0.40 × 100) — what they ACTUALLY did
    - Skill Trust:       35 pts max (0.35 × 100) — verified skill relevance
    - Semantic Match:    25 pts max (0.25 × 100) — pre-computed embedding similarity

    WHY these weights:
    - Career evidence is most important: shows real production experience
    - Skill trust is second: validated skills matter more than listed skills
    - Semantic is supporting: catches nuanced relevance that keywords miss

    Args:
        candidate: candidate dict from candidates.jsonl
        semantic_score: cosine similarity score 0-100 (pre-computed in rank.py)

    Returns:
        float 0-100 capability score
    """
    career_ev = career_evidence_score(candidate)       # 0-50 range
    skill_tr = skill_trust_score(candidate)            # 0-100 range
    sem = max(0.0, min(100.0, semantic_score))         # 0-100 range

    score = (
        (career_ev / 50.0) * 40.0    # Scale 0-50 → 40 point max
        + (skill_tr / 100.0) * 35.0  # Scale 0-100 → 35 point max
        + (sem / 100.0) * 25.0       # Scale 0-100 → 25 point max
    )

    return min(100.0, max(0.0, score))
