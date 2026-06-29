"""
core/disqualifier.py — FHire Hard Disqualifiers

WHY THIS FILE EXISTS:
  Before we spend any time scoring a candidate, we HARD-FILTER the obvious
  rejections. This serves two purposes:
    1. Speed: Less candidates to score → faster runtime
    2. Accuracy: Ensures no honeypot or irrelevant candidate pollutes top 100

  There are ~80 "honeypot" candidates in the dataset with impossible profiles.
  The organizers told us: if ANY honeypot appears in our top 10 at Stage 3,
  we are DISQUALIFIED. So this filter runs FIRST, always.

  There are also JD-explicit disqualifiers — things the job description
  explicitly said we should reject (e.g. pure consulting careers,
  CV/Speech-only candidates with no NLP background).

HOW IT WORKS:
  is_disqualified(candidate) → (True, "reason") or (False, None)
  
  Called first in rank.py for every candidate.
  If True → skip this candidate entirely, don't score.
"""

# ─── CONSTANTS ────────────────────────────────────────────────────────────────

# Consulting-only firms: JD explicitly said pure consulting = disqualified
CONSULTING_FIRMS = [
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
    "ltimindtree", "mindtree", "birlasoft", "niit technologies",
    "mastech", "syntel", "patni"
]

# Keywords that indicate CV/Speech-only domain (not NLP/IR)
CV_SPEECH_KEYWORDS = [
    "computer vision", "image classif", "speech recognition",
    "object detection", "tts", "asr", "robotics", "image segmentation",
    "pose estimation", "face recognition", "optical character"
]

# Keywords that indicate NLP / Information Retrieval relevance
NLP_IR_KEYWORDS = [
    "nlp", "embedding", "retrieval", "ranking", "search",
    "language model", "transformer", "llm", "rag", "information retrieval",
    "semantic search", "vector", "text classification", "named entity"
]

# Titles that are clearly irrelevant (no ML path = disqualify)
IRRELEVANT_TITLES = [
    "marketing manager", "sales executive", "graphic designer",
    "content writer", "accountant", "hr manager", "customer support",
    "civil engineer", "mechanical engineer", "business analyst",
    "operations manager", "financial analyst", "ui/ux designer",
    "product designer", "social media", "seo specialist", "copywriter",
    "office manager", "executive assistant", "recruiter"
]

# Career description keywords that show ML background (saves irrelevant-title candidates)
ML_CAREER_KEYWORDS = [
    "machine learning", "neural", "embedding", "nlp",
    "recommendation", "retrieval", "ranking", "model training",
    "ai ", " ml ", "deep learning", "transformer", "fine-tun",
    "vector database", "llm", "rag", "prediction", "classification"
]


# ─── HONEYPOT DETECTORS ───────────────────────────────────────────────────────

def _has_expert_zero_duration_honeypot(candidate: dict) -> bool:
    """
    Honeypot type 1: Expert-level skill claimed with 0 months usage.
    No real person is "Expert" in a skill they've used for 0 months.
    Threshold: 3 or more such skills → definitely a fake profile.
    """
    skills = candidate.get("skills", [])
    zero_experts = sum(
        1 for s in skills
        if s.get("proficiency") == "expert" and s.get("duration_months", 1) == 0
    )
    return zero_experts >= 3


def _has_impossible_career_duration(candidate: dict) -> bool:
    """
    Honeypot type 2: A role's duration_months exceeds what's possible
    given the candidate's total years_of_experience.

    Example: 8 years at a company that was founded only 3 years ago.
    We add 18 months buffer to be fair (profile could be slightly off).
    """
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    max_possible_months = (yoe * 12) + 18  # generous buffer

    for role in candidate.get("career_history", []):
        if role.get("duration_months", 0) > max_possible_months:
            return True
    return False


def _has_expert_experience_mismatch_honeypot(candidate: dict) -> bool:
    """
    Honeypot type 3: Too many expert skills for very low experience.
    8+ expert skills with under 4 years of experience is unrealistic.
    Real experts take years to reach expert-level in even one domain.
    """
    skills = candidate.get("skills", [])
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)
    expert_count = sum(1 for s in skills if s.get("proficiency") == "expert")
    return expert_count >= 8 and yoe < 4


# ─── JD-EXPLICIT DISQUALIFIERS ────────────────────────────────────────────────

def _is_pure_consulting(candidate: dict) -> bool:
    """
    JD explicit: "Entire career in consulting = disqualified."
    Candidates who've only worked at TCS, Infosys, Wipro, etc. their
    entire career have no product-building experience.

    Only triggers if the candidate has 2+ roles (not brand new).
    """
    career = candidate.get("career_history", [])
    if len(career) < 2:
        return False  # Only 1 role — not enough data to call "entire career"

    non_consulting_roles = sum(
        1 for r in career
        if not any(firm in r.get("company", "").lower() for firm in CONSULTING_FIRMS)
    )
    return non_consulting_roles == 0


def _is_cv_speech_only_no_nlp(candidate: dict) -> bool:
    """
    JD explicit: "CV/Speech domain with no NLP/IR = wrong fit."
    This JD needs NLP, retrieval, ranking. Pure computer vision or
    speech recognition engineers without NLP/IR skills are irrelevant.

    Only disqualifies if: 3+ CV/speech skills AND zero NLP/IR skills.
    """
    skill_names = " ".join(s.get("name", "").lower() for s in candidate.get("skills", []))

    cv_count = sum(1 for kw in CV_SPEECH_KEYWORDS if kw in skill_names)
    nlp_count = sum(1 for kw in NLP_IR_KEYWORDS if kw in skill_names)

    return cv_count >= 3 and nlp_count == 0


def _is_irrelevant_title_no_ml_history(candidate: dict) -> bool:
    """
    JD explicit: "HR Managers, Accountants, etc. are irrelevant."
    HOWEVER — we give them a chance: if their career descriptions show
    ML work (e.g. a former Content Writer who transitioned to ML), keep them.

    Only disqualifies if: irrelevant current title + NO ML evidence in career.
    """
    current_title = candidate.get("profile", {}).get("current_title", "").lower()

    # Check if current title is in our irrelevant list
    is_irrelevant = any(t in current_title for t in IRRELEVANT_TITLES)
    if not is_irrelevant:
        return False  # Title is fine → don't disqualify

    # Irrelevant title found — but check career for ML evidence
    all_desc = " ".join(
        r.get("description", "").lower()
        for r in candidate.get("career_history", [])
    )
    # Also check summary
    summary = candidate.get("profile", {}).get("summary", "").lower()
    combined_text = all_desc + " " + summary

    has_ml = any(kw in combined_text for kw in ML_CAREER_KEYWORDS)
    return not has_ml  # Disqualify only if no ML evidence found


# ─── MAIN DISQUALIFIER ────────────────────────────────────────────────────────

def is_disqualified(candidate: dict) -> tuple[bool, str | None]:
    """
    Main disqualifier — runs ALL checks in order, fast-fails on first hit.

    Order matters: honeypot checks run first (fastest, most certain).
    JD checks run after (slightly more nuanced).

    Args:
        candidate: a single candidate dict from candidates.jsonl

    Returns:
        (True, "reason string")  → disqualified, skip this candidate
        (False, None)            → passed all checks, proceed to scoring

    Usage in rank.py:
        disq, reason = is_disqualified(candidate)
        if disq:
            continue
    """

    # ── HONEYPOT CHECKS (binary — either fake or not) ─────────────────────────

    if _has_expert_zero_duration_honeypot(candidate):
        return True, "honeypot: 3+ expert skills with 0 months duration"

    if _has_impossible_career_duration(candidate):
        return True, "honeypot: career duration exceeds total years of experience"

    if _has_expert_experience_mismatch_honeypot(candidate):
        return True, "honeypot: 8+ expert skills with under 4 years experience"

    # ── JD-EXPLICIT DISQUALIFIERS ─────────────────────────────────────────────

    if _is_pure_consulting(candidate):
        return True, "disqualified: entire career in consulting firms (JD explicit)"

    if _is_cv_speech_only_no_nlp(candidate):
        return True, "disqualified: CV/Speech domain only, no NLP/IR skills (JD explicit)"

    if _is_irrelevant_title_no_ml_history(candidate):
        title = candidate.get("profile", {}).get("current_title", "unknown")
        return True, f"disqualified: irrelevant title '{title}', no ML career evidence"

    # ── ALL CHECKS PASSED ─────────────────────────────────────────────────────

    return False, None


def disqualify_batch(candidates: list) -> tuple[list, dict]:
    """
    Run disqualifier on a batch of candidates.
    Returns (qualified_candidates, stats_dict).

    Used for analytics/reporting.
    """
    qualified = []
    stats = {}

    for c in candidates:
        disq, reason = is_disqualified(c)
        if disq:
            # Group by reason category for reporting
            category = reason.split(":")[0] if reason else "unknown"
            stats[category] = stats.get(category, 0) + 1
        else:
            qualified.append(c)

    return qualified, stats
