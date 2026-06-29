"""
core/trajectory_engine.py — FHire Trajectory Score (Dimension 2, 25%)

WHY THIS FILE EXISTS:
  "Are they growing in the right direction?"

  This is the BIGGEST differentiator from other teams. Most teams will look at:
  - Current title
  - Skills list
  That's it. They'll completely ignore career history.

  We analyze the ENTIRE career arc:
  1. Direction: Is the candidate's title progression moving TOWARD AI Engineering?
     Backend → Search → Ranking → AI Engineer = STRONG (trajectory pointing at JD)
     ML Engineer → ML Engineer → ML Engineer = FLAT (no growth)
     ML Engineer → Data Analyst → Marketing = WRONG WAY (moving away from AI)

  2. Velocity: How fast are they progressing?
     Promoted within same company? Hit Senior level fast? = Fast tracker

  3. Tenure Stability: JD explicitly said "1.5 year switchers = not a fit"
     Average tenure under 18 months = job hopper penalty

  4. Career DNA: A label for each candidate's career pattern
     - "Startup Builder" = worked at small companies, shipped real products → IDEAL
     - "Scale Expert" = big tech, handled real scale
     - "Research Specialist" = only papers, no deployment → JD explicit disqualifier
     - "Consulting Only" = already handled in disqualifier

  Final trajectory_score = direction×0.50 + velocity×0.30 + tenure×0.20
  With DNA multiplier applied on top.

HOW IT CONNECTS:
  - Called from rank.py and pipeline.py per candidate
  - Returns dict with score + breakdown for reasoning and frontend display
"""

# ─── TITLE RELEVANCE MAP ──────────────────────────────────────────────────────
# Maps role titles to their relevance to the Senior AI Engineer JD.
# Scale 0-10, where 10 = perfect title match for this specific role.
# Used to track whether candidate is trending toward or away from AI Engineering.

TITLE_RELEVANCE_SCORES = {
    # Tier 5 — Perfect match (9-10): These ARE the role
    "senior ai engineer": 10,
    "senior ml engineer": 10,
    "staff machine learning": 10,
    "lead ai engineer": 10,
    "applied ml engineer": 9,
    "principal ml": 10,
    "principal ai": 10,
    "senior machine learning": 10,
    "ai research engineer": 9,
    "ml platform engineer": 9,
    "staff ai": 10,

    # Tier 4 — Strong match (7-8): Directly relevant
    "ml engineer": 8,
    "machine learning engineer": 8,
    "ai engineer": 8,
    "nlp engineer": 9,
    "nlp scientist": 9,
    "data scientist": 7,
    "ai specialist": 7,
    "applied scientist": 8,
    "research scientist": 7,  # Note: pure research = DNA penalty later
    "junior ml engineer": 6,
    "junior ai engineer": 6,
    "computer vision engineer": 5,  # Adjacent, but wrong specialization

    # Tier 3 — Growing toward it (4-7): Has relevant adjacent skills
    "search engineer": 7,
    "ranking engineer": 8,
    "recommendation engineer": 7,
    "recommendation systems": 7,
    "senior software engineer": 5,
    "backend engineer": 4,
    "platform engineer": 4,
    "infrastructure engineer": 4,
    "data engineer": 4,

    # Tier 2 — Possible pivot (2-4): Could be relevant with right background
    "analytics engineer": 3,
    "software engineer": 3,
    "full stack": 2,
    "devops": 2,
    "cloud engineer": 2,
    "sre": 2,

    # Tier 1 — Wrong direction (0): Actively irrelevant
    "marketing manager": 0,
    "hr manager": 0,
    "accountant": 0,
    "content writer": 0,
    "civil engineer": 0,
    "mechanical engineer": 0,
    "graphic designer": 0,
    "sales executive": 0,
    "business analyst": 1,
    "product manager": 2,  # PM = some tech exposure
}

# Companies that indicate big tech / known product companies (Scale Expert DNA)
BIG_TECH_AND_PRODUCT_COMPANIES = [
    "google", "meta", "facebook", "microsoft", "amazon", "apple",
    "netflix", "uber", "airbnb", "twitter", "x corp",
    # Indian product companies
    "flipkart", "zomato", "swiggy", "razorpay", "phonepe", "meesho",
    "cred", "byju", "unacademy", "groww", "zepto", "zerodha",
    "nykaa", "paytm", "ola", "dunzo", "urban company",
    "myntra", "snapdeal", "pepperfry", "lenskart",
    # Other strong companies
    "openai", "anthropic", "cohere", "hugging face", "mistral",
    "databricks", "snowflake", "stripe", "shopify",
]

# Small startup sizes (product-builder DNA)
STARTUP_SIZES = ["1-10", "11-50", "51-200"]

# Research signals in career descriptions
RESEARCH_SIGNALS = [
    "paper", "published", "research", "arxiv", "phd", "thesis",
    "conference", "journal", "ieee", "acl", "emnlp", "neurips", "icml"
]

# Production deployment signals
PRODUCTION_SIGNALS = [
    "deployed", "production", "real users", "serving", "shipped",
    "launched", "release", "live", "customers use"
]

# Consulting firms (for DNA classification)
CONSULTING_FIRMS_DNA = [
    "tcs", "infosys", "wipro", "accenture", "cognizant",
    "capgemini", "hcl", "tech mahindra", "mphasis", "hexaware",
    "ltimindtree", "mindtree", "birlasoft", "niit", "mastech"
]


# ─── COMPONENT 1: DIRECTION SCORE ─────────────────────────────────────────────

def get_title_relevance(title: str) -> float:
    """
    Maps a job title string to its AI Engineering relevance score (0-10).
    Uses substring matching so "Senior ML Engineer at Flipkart" → matches "ml engineer" → 8.

    Falls back to 2 for unknown titles (gives small base score).
    """
    title_lower = title.lower().strip()
    for key, val in TITLE_RELEVANCE_SCORES.items():
        if key in title_lower:
            return float(val)
    return 2.0  # Unknown title → small base score, not zero


def direction_score(career_history: list) -> float:
    """
    Measures whether the candidate's career trajectory is pointing
    TOWARD AI Engineering or away from it.

    Method:
    1. Sort career chronologically (earliest to latest)
    2. Get relevance score for each role title
    3. Compare recent roles vs early roles
    4. Big positive delta = moving toward AI = high score

    Example:
        Backend Engineer (3) → Search Engineer (7) → AI Engineer (8)
        recent_avg = (7+8)/2 = 7.5, early_avg = 3.0, delta = +4.5 → Score: 95

    Returns:
        float 0-100 direction score
    """
    if len(career_history) < 2:
        return 55.0  # Not enough data to determine direction → neutral

    # Sort chronologically: earliest first
    sorted_career = sorted(career_history, key=lambda r: r.get("start_date", ""), reverse=False)
    relevance_over_time = [get_title_relevance(r.get("title", "")) for r in sorted_career]

    n = len(relevance_over_time)

    # Recent = last 2 roles, Early = everything before last 2
    recent_avg = sum(relevance_over_time[-2:]) / 2.0
    early_count = max(1, n - 2)
    early_avg = sum(relevance_over_time[:n - 2]) / early_count if n > 2 else relevance_over_time[0]

    direction_delta = recent_avg - early_avg

    # Classify trajectory
    if direction_delta > 4:
        return 95.0   # Strong upward: Backend → Search → Ranking → AI
    elif direction_delta > 3:
        return 88.0
    elif direction_delta > 2:
        return 80.0
    elif direction_delta > 1:
        return 70.0
    elif direction_delta > 0:
        return 65.0   # Slight upward or flat but relevant
    elif direction_delta == 0 and recent_avg >= 7:
        return 62.0   # Flat but already at high relevance level
    elif direction_delta == 0 and recent_avg >= 5:
        return 50.0   # Flat at medium relevance
    elif direction_delta < -3:
        return 20.0   # Moving AWAY from AI engineering
    elif direction_delta < -1:
        return 30.0
    else:
        return 40.0   # Slight downward or unclear


# ─── COMPONENT 2: VELOCITY SCORE ──────────────────────────────────────────────

def velocity_score(career_history: list, years_of_experience: float) -> float:
    """
    Measures how FAST the candidate is progressing in their career.

    Fast trackers are better hires: they show ambition, performance, and
    the ability to grow quickly (important for a startup's first AI hire).

    Signals:
    - Promotions at same company: if relevance score increased in same company
    - Senior level achieved early: Senior/Staff/Lead with < 6 years experience

    Returns:
        float 0-100 velocity score (baseline 50)
    """
    promotions = 0
    companies_seen = {}  # company → best relevance score at that company so far

    for role in sorted(career_history, key=lambda r: r.get("start_date", "")):
        company = role.get("company", "").lower().strip()
        curr_relevance = get_title_relevance(role.get("title", ""))

        if company in companies_seen:
            prev_relevance = companies_seen[company]
            if curr_relevance > prev_relevance + 1:  # Meaningful step up
                promotions += 1
        companies_seen[company] = max(companies_seen.get(company, 0), curr_relevance)

    # Current title seniority
    current_title = career_history[-1].get("title", "").lower() if career_history else ""
    is_senior = any(x in current_title for x in ["senior", "staff", "lead", "principal", "head", "vp", "director"])

    velocity = 50.0  # Baseline

    if promotions >= 3:
        velocity += 30
    elif promotions == 2:
        velocity += 20
    elif promotions == 1:
        velocity += 12

    # Fast tracker: reached senior level quickly
    if is_senior and years_of_experience <= 5:
        velocity += 25   # Very fast tracker
    elif is_senior and years_of_experience <= 7:
        velocity += 15
    elif is_senior and years_of_experience <= 9:
        velocity += 8

    return min(100.0, velocity)


# ─── COMPONENT 3: TENURE STABILITY SCORE ─────────────────────────────────────

def tenure_score(career_history: list) -> float:
    """
    JD explicit: "Title-chasers who switch every 1.5 years — we're not a fit.
    We need someone who plans to be here 3+ years."

    Calculates average tenure per company. Under 18 months average = job hopper.

    Note: This is average per role, not total. A single 5-year role followed by
    a recent short stint is not a "job hopper" — we're fair here.

    Returns:
        float 0-100 tenure stability score
    """
    if len(career_history) < 2:
        return 70.0  # Not enough data → give benefit of doubt

    total_months = sum(r.get("duration_months", 0) for r in career_history)
    avg_tenure = total_months / len(career_history)

    if avg_tenure < 10:
        return 5.0    # Extreme job hopper (< 10 months average)
    elif avg_tenure < 18:
        return 25.0   # JD explicit: "switching every 1.5 years = not a fit"
    elif avg_tenure < 24:
        return 50.0   # Below ideal but acceptable
    elif avg_tenure < 30:
        return 68.0
    elif avg_tenure < 36:
        return 80.0
    elif avg_tenure < 48:
        return 90.0
    else:
        return 100.0  # Very stable — exactly what JD wants (3+ years per role)


# ─── COMPONENT 4: CAREER DNA CLASSIFICATION ───────────────────────────────────

def classify_career_dna(candidate: dict) -> str:
    """
    Classifies the candidate into one of 5 career "DNA" archetypes.
    Used for dashboard display, reasoning generation, and scoring multiplier.

    DNA types (in priority order):
    - "Startup Builder"     = worked at small companies + production evidence → IDEAL
    - "Scale Expert"        = big tech/large product companies + scale evidence
    - "Product Engineer"    = product companies, real deployment, good general signal
    - "Research Specialist" = only papers, no production → JD explicit downgrade
    - "Consulting Only"     = service firms only → already filtered, but catch any remaining
    - "Career Switcher"     = was in unrelated field, now in AI (rising signal)
    - "Unclear"             = can't classify with confidence

    Returns:
        str: one of the DNA type strings above
    """
    career = candidate.get("career_history", [])
    all_desc = " ".join(r.get("description", "").lower() for r in career)
    companies = [r.get("company", "").lower() for r in career]
    sizes = [r.get("company_size", "") for r in career]

    # Boolean signals
    has_startup = any(s in STARTUP_SIZES for s in sizes)
    has_big_tech = any(
        any(tech in company for tech in BIG_TECH_AND_PRODUCT_COMPANIES)
        for company in companies
    )
    has_research = any(kw in all_desc for kw in RESEARCH_SIGNALS)
    has_production = any(kw in all_desc for kw in PRODUCTION_SIGNALS)
    has_consulting_only = all(
        any(c in company for c in CONSULTING_FIRMS_DNA)
        for company in companies
    ) and len(companies) >= 2

    # DNA classification priority order
    if has_consulting_only:
        return "Consulting Only"
    elif has_research and not has_production:
        return "Research Specialist"   # Papers only, never shipped → JD downgrade
    elif has_production and has_startup:
        return "Startup Builder"       # Shipped at startups → IDEAL for Series A
    elif has_production and has_big_tech:
        return "Scale Expert"          # Shipped at big tech → handled real scale
    elif has_production:
        return "Product Engineer"      # Shipped somewhere → solid signal
    elif has_research:
        return "Research Specialist"   # Has research, some production might exist
    else:
        return "Unclear"


# ─── FINAL TRAJECTORY SCORE ───────────────────────────────────────────────────

def trajectory_score_final(candidate: dict) -> dict:
    """
    Combines all trajectory components into a final score with breakdown.

    Weights:
    - Direction: 50% (most important — which way are they going?)
    - Velocity:  30% (how fast are they growing?)
    - Tenure:    20% (how stable are they?)

    DNA multiplier applied AFTER combining:
    - Research Specialist (no production): 0.35 — JD explicit penalize
    - Consulting Only: 0.50 — negative signal
    - All others: 1.0 — full score

    Returns dict (not just float) so frontend and reasoning generator
    can use breakdown components.

    Returns:
        {
          "score": float 0-100,
          "dna": str career DNA classification,
          "direction": float 0-100,
          "velocity": float 0-100,
          "tenure": float 0-100,
          "tenure_avg_months": float average months per role,
          "is_job_hopper": bool (avg tenure < 18 months),
          "dna_multiplier": float applied multiplier
        }
    """
    career = candidate.get("career_history", [])
    yoe = candidate.get("profile", {}).get("years_of_experience", 0)

    # Calculate components
    direction = direction_score(career)
    velocity = velocity_score(career, yoe)
    tenure = tenure_score(career)
    dna = classify_career_dna(candidate)

    # Career tenure average for reasoning
    avg_tenure_months = (
        sum(r.get("duration_months", 0) for r in career) / len(career)
        if career else 0
    )

    # DNA multiplier
    dna_multiplier = 1.0
    if dna == "Research Specialist":
        dna_multiplier = 0.35  # JD explicit: "pure researchers aren't a fit"
    elif dna == "Consulting Only":
        dna_multiplier = 0.50  # Strong negative signal

    # Raw score before multiplier
    raw = (
        direction * 0.50
        + velocity  * 0.30
        + tenure    * 0.20
    )

    final = min(100.0, raw * dna_multiplier)

    return {
        "score": final,
        "dna": dna,
        "direction": direction,
        "velocity": velocity,
        "tenure": tenure,
        "tenure_avg_months": avg_tenure_months,
        "is_job_hopper": avg_tenure_months < 18,
        "dna_multiplier": dna_multiplier,
    }
