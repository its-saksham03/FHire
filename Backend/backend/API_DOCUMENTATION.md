# FHire — API Documentation

**Version:** 4.0  
**Base URL (local):** `http://localhost:8000`  
**Base URL (deployed):** Set via `NEXT_PUBLIC_API_URL` in your Vercel environment.

All endpoints are prefixed with `/api`.  
All request and response bodies are JSON.

---

## Table of Contents

1. [GET /api/health](#1-get-apihealth)
2. [POST /api/rank](#2-post-apirank)
3. [GET /api/candidate/{candidate_id}](#3-get-apicandidatecandidate_id)
4. [POST /api/compare](#4-post-apicompare)
5. [GET /api/stats](#5-get-apistats)
6. [Common Data Shapes](#6-common-data-shapes)
7. [Integration Quick-Start for Member 3](#7-integration-quick-start-for-member-3)

---

## 1. GET /api/health

**Purpose:** Confirm the server is running and check which assets are loaded.  
**Call this first** to verify the backend is reachable before making other requests.

### Request
No body required.

```
GET /api/health
```

### Response `200 OK`

```json
{
  "status": "ok",
  "version": "4.0",
  "embeddings_loaded": true,
  "distributions_loaded": true,
  "ranked_pool_size": 0
}
```

| Field | Type | Description |
|---|---|---|
| `status` | string | Always `"ok"` when server is up |
| `version` | string | Backend version |
| `embeddings_loaded` | boolean | True if `data/embeddings.npz` was found at startup |
| `distributions_loaded` | boolean | True if `data/distributions.json` was found at startup |
| `ranked_pool_size` | integer | Number of candidates in the in-memory ranked pool (0 until POST /rank is called) |

---

## 2. POST /api/rank

**Purpose:** Score and rank a list of raw candidate dicts. Returns a fully ranked list with all dimension scores, reasoning, and optional counterfactuals.

This is the **main endpoint**. The rankings page is populated from this response.

> **Note:** Call this before `/candidate` or `/compare` — those endpoints look up candidates from the ranked pool populated by this call.

### Request Body

```json
{
  "candidates": [ ...up to 100 candidate dicts... ],
  "include_counterfactual": false
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `candidates` | array | ✅ | Raw candidate dicts in `candidates.jsonl` format (1–100 items) |
| `include_counterfactual` | boolean | ❌ | Default `false`. Set `true` to include "what would it take" output. Adds ~200ms. |

**Candidate dict structure** (from `candidates.jsonl`):
```json
{
  "candidate_id": "CAND_0002025",
  "profile": {
    "current_title": "Senior AI Engineer",
    "years_of_experience": 5.9,
    "location": "Bangalore",
    "country": "India",
    "headline": "...",
    "summary": "..."
  },
  "career_history": [
    {
      "title": "ML Engineer",
      "company": "Paytm",
      "start_date": "2021-01",
      "duration_months": 24,
      "description": "Built production RAG serving...",
      "company_size": "1001-5000"
    }
  ],
  "skills": [
    {
      "name": "RAG",
      "proficiency": "expert",
      "endorsements": 14,
      "duration_months": 18
    }
  ],
  "redrob_signals": {
    "open_to_work_flag": true,
    "last_active_date": "2026-06-20",
    "recruiter_response_rate": 0.80,
    "interview_completion_rate": 0.75,
    "avg_response_time_hours": 6.0,
    "notice_period_days": 30,
    "willing_to_relocate": true,
    "preferred_work_mode": "hybrid",
    "github_activity_score": 97,
    "profile_completeness_score": 88,
    "verified_email": true,
    "verified_phone": true,
    "skill_assessment_scores": { "RAG": 84 },
    "saved_by_recruiters_30d": 5,
    "endorsements_received": 22,
    "connection_count": 310
  }
}
```

### Response `200 OK`

```json
{
  "total_scored": 45,
  "total_disqualified": 5,
  "results": [
    {
      "candidate_id": "CAND_0002025",
      "rank": 1,
      "final_score": 0.664274,
      "capability": 78.3,
      "trajectory": {
        "score": 82.5,
        "dna": "Startup Builder",
        "direction": 95.0,
        "velocity": 75.0,
        "tenure": 68.0,
        "tenure_avg_months": 26.4,
        "is_job_hopper": false,
        "dna_multiplier": 1.0
      },
      "recruitability": {
        "score": 74.2,
        "multiplier": 0.768,
        "breakdown": {
          "availability": 35.0,
          "responsiveness": 25.1,
          "logistics": 14.1
        }
      },
      "authenticity": {
        "score": 90.0,
        "flags": []
      },
      "confidence": {
        "score": 78,
        "label": "High",
        "explanation": "Strong evidence base: multiple validated signals..."
      },
      "reasoning": "Senior AI Engineer with 5.9yrs; career DNA: Startup Builder; at Apple: ...; actively looking; 30d notice; responsive (80% response rate); active GitHub (97/100).",
      "counterfactual": null,
      "career_dna": "Startup Builder"
    }
  ]
}
```

| Field | Type | Description |
|---|---|---|
| `total_scored` | integer | Candidates that passed disqualification and were scored |
| `total_disqualified` | integer | Candidates removed by the hard disqualifier |
| `results` | array | Ranked candidates, index 0 = rank 1 |
| `results[].candidate_id` | string | Candidate ID |
| `results[].rank` | integer | 1-based rank |
| `results[].final_score` | float | Final score in 0–1 range (multiply by 100 for display) |
| `results[].capability` | float | Capability score 0–100 |
| `results[].trajectory` | object | Full trajectory breakdown (see [Trajectory Shape](#trajectory)) |
| `results[].recruitability` | object | Full recruitability breakdown (see [Recruitability Shape](#recruitability)) |
| `results[].authenticity` | object | Authenticity score + flags |
| `results[].confidence` | object | Confidence score, label, explanation |
| `results[].reasoning` | string | Grounded recruiter-style reasoning sentence |
| `results[].counterfactual` | object \| null | Counterfactual output if `include_counterfactual=true`, else `null` |
| `results[].career_dna` | string | Career DNA label (pulled from trajectory for easy access) |

---

## 3. GET /api/candidate/{candidate_id}

**Purpose:** Return the complete score breakdown for a single candidate. Powers the Candidate Detail page.

> Requires POST /api/rank to have been called first.

### Request

```
GET /api/candidate/CAND_0002025
```

### Response `200 OK`

```json
{
  "candidate_id": "CAND_0002025",
  "rank": 1,
  "final_score": 0.664274,
  "capability": 78.3,
  "trajectory": { ... },
  "recruitability": { ... },
  "authenticity": {
    "score": 90.0,
    "flags": []
  },
  "confidence": {
    "score": 78,
    "label": "High",
    "explanation": "Strong evidence base..."
  },
  "reasoning": "Senior AI Engineer with 5.9yrs; ...",
  "counterfactual": {
    "current_rank": 1,
    "current_score": 0.664274,
    "top_improvements": [
      {
        "change": "Mark profile as Open to Work",
        "rank_improvement": 0,
        "score_delta": 0.0,
        "feasibility": "Can do immediately"
      }
    ],
    "summary": "Candidate is already near-optimal on recruitability signals (rank #1)."
  },
  "career_dna": "Startup Builder",
  "profile": {
    "current_title": "Senior AI Engineer",
    "years_of_experience": 5.9,
    "location": "Bangalore",
    "country": "India"
  },
  "signals": {
    "open_to_work_flag": true,
    "notice_period_days": 30,
    "recruiter_response_rate": 0.80,
    "github_activity_score": 97
  }
}
```

### Response `404 Not Found`

```json
{
  "detail": "Candidate 'CAND_XXXXXX' not found in ranked pool. Call POST /api/rank first."
}
```

| Field | Type | Description |
|---|---|---|
| `profile` | object | Raw profile fields — use for display (title, location, YoE) |
| `signals` | object | Raw redrob_signals — use for availability indicators |
| All other fields | — | Same as in `/rank` response |

---

## 4. POST /api/compare

**Purpose:** Explain why Candidate A ranked above Candidate B. Powers the Compare page.

Accepts either two candidate IDs (recommended — looked up from ranked pool) or two full score dicts.

### Request Body — by ID (recommended)

```json
{
  "candidate_a_id": "CAND_0002025",
  "candidate_b_id": "CAND_0046132"
}
```

### Request Body — by score dicts (alternative)

```json
{
  "scores_a": { ...full score dict from /rank results... },
  "scores_b": { ...full score dict from /rank results... }
}
```

> Pass **either** IDs **or** dicts. Mixing is not supported.

### Response `200 OK`

```json
{
  "candidate_a": {
    "candidate_id": "CAND_0002025",
    "current_title": "Senior AI Engineer",
    "location": "Bangalore",
    "years_of_experience": 5.9,
    "career_dna": "Startup Builder",
    "notice_period": 30,
    "open_to_work": true,
    "confidence_label": "High"
  },
  "candidate_b": {
    "candidate_id": "CAND_0046132",
    "current_title": "AI Research Engineer",
    "location": "Mumbai",
    "years_of_experience": 4.3,
    "career_dna": "Startup Builder",
    "notice_period": 30,
    "open_to_work": true,
    "confidence_label": "Medium"
  },
  "final_score_a": 66.4274,
  "final_score_b": 64.7114,
  "final_score_diff": 1.716,
  "dimension_comparisons": [
    {
      "dimension": "Capability",
      "score_a": 78.3,
      "score_b": 71.2,
      "difference": 7.1,
      "advantage": "slight advantage",
      "winner": "A"
    },
    {
      "dimension": "Trajectory",
      "score_a": 82.5,
      "score_b": 85.0,
      "difference": -2.5,
      "advantage": "roughly equal",
      "winner": "tie"
    },
    {
      "dimension": "Recruitability",
      "score_a": 74.2,
      "score_b": 72.8,
      "difference": 1.4,
      "advantage": "roughly equal",
      "winner": "tie"
    },
    {
      "dimension": "Authenticity",
      "score_a": 90.0,
      "score_b": 88.0,
      "difference": 2.0,
      "advantage": "roughly equal",
      "winner": "tie"
    },
    {
      "dimension": "Confidence",
      "score_a": 78,
      "score_b": 65,
      "difference": 13,
      "advantage": "slight advantage",
      "winner": "A"
    }
  ],
  "dimensions_a_wins": ["Capability", "Confidence"],
  "dimensions_b_wins": [],
  "verdict": "CAND_0002025 ranked higher due to stronger Capability, Confidence. Final score gap: 1.7 pts.",
  "reasoning_a": "Senior AI Engineer with 5.9yrs; career DNA: Startup Builder; ...",
  "reasoning_b": "AI Research Engineer with 4.3yrs; career DNA: Startup Builder; ..."
}
```

| Field | Type | Description |
|---|---|---|
| `candidate_a` / `candidate_b` | object | Display metadata for each candidate |
| `final_score_a` / `final_score_b` | float | Scores on 0–100 scale |
| `final_score_diff` | float | A minus B (positive = A leads) |
| `dimension_comparisons` | array | Per-dimension breakdown (5 entries) |
| `dimension_comparisons[].advantage` | string | `"clear advantage"` \| `"slight advantage"` \| `"roughly equal"` \| `"slight disadvantage"` \| `"clear disadvantage"` |
| `dimension_comparisons[].winner` | string | `"A"` \| `"B"` \| `"tie"` |
| `dimensions_a_wins` | array | Dimension names where A clearly leads (diff > 5 pts) |
| `dimensions_b_wins` | array | Dimension names where B clearly leads |
| `verdict` | string | Human-readable recruiter explanation |
| `reasoning_a` / `reasoning_b` | string | Grounded reasoning strings from /rank |

### Response `404 Not Found`

```json
{
  "detail": "Candidate 'CAND_XXXXXX' not found in ranked pool."
}
```

### Response `422 Unprocessable Entity`

```json
{
  "detail": "Provide either (candidate_a_id + candidate_b_id) or (scores_a + scores_b)."
}
```

---

## 5. GET /api/stats

**Purpose:** Aggregate statistics over the current ranked pool. Powers the Analytics page charts.

Returns zeroed stats if POST /api/rank has not been called yet.

### Request

```
GET /api/stats
```

### Response `200 OK`

```json
{
  "total_ranked": 100,
  "disqualified_count": 72431,
  "avg_capability": 61.4,
  "avg_trajectory": 58.2,
  "avg_recruitability": 69.8,
  "avg_authenticity": 87.3,
  "avg_notice_period_days": 38.5,
  "open_to_work_count": 84,
  "dna_distribution": {
    "Startup Builder": 34,
    "Scale Expert": 28,
    "Product Engineer": 18,
    "Research Specialist": 4,
    "Consulting Only": 2,
    "Unclear": 14
  },
  "confidence_distribution": {
    "High": 45,
    "Medium": 38,
    "Low": 17
  },
  "score_buckets": {
    "0.0-0.2": 0,
    "0.2-0.4": 3,
    "0.4-0.6": 61,
    "0.6-0.8": 36,
    "0.8-1.0": 0
  }
}
```

| Field | Type | Description |
|---|---|---|
| `total_ranked` | integer | Candidates in the ranked pool |
| `disqualified_count` | integer | Candidates removed by hard disqualifier |
| `avg_capability` | float | Mean capability score across ranked pool |
| `avg_trajectory` | float | Mean trajectory score |
| `avg_recruitability` | float | Mean recruitability score |
| `avg_authenticity` | float | Mean authenticity score |
| `avg_notice_period_days` | float | Mean notice period in days |
| `open_to_work_count` | integer | Candidates with open_to_work_flag = true |
| `dna_distribution` | object | Count per Career DNA category |
| `confidence_distribution` | object | Count per `"High"` / `"Medium"` / `"Low"` |
| `score_buckets` | object | Histogram of final scores (multiplied by 100 for binning) |

---

## 6. Common Data Shapes

### Trajectory

```json
{
  "score": 82.5,
  "dna": "Startup Builder",
  "direction": 95.0,
  "velocity": 75.0,
  "tenure": 68.0,
  "tenure_avg_months": 26.4,
  "is_job_hopper": false,
  "dna_multiplier": 1.0
}
```

**Career DNA values:** `"Startup Builder"` | `"Scale Expert"` | `"Product Engineer"` | `"Research Specialist"` | `"Consulting Only"` | `"Unclear"`

### Recruitability

```json
{
  "score": 74.2,
  "multiplier": 0.768,
  "breakdown": {
    "availability": 35.0,
    "responsiveness": 25.1,
    "logistics": 14.1
  }
}
```

### Authenticity

```json
{
  "score": 90.0,
  "flags": [
    "skill_inflation: RAG — claimed expert, assessment scored 42/100"
  ]
}
```

Flags are empty `[]` when the profile is clean.

### Confidence

```json
{
  "score": 78,
  "label": "High",
  "explanation": "Strong evidence base: multiple validated signals, engines are in agreement."
}
```

**Label values:** `"High"` | `"Medium"` | `"Low"`

### Counterfactual

```json
{
  "current_rank": 47,
  "current_score": 0.495092,
  "top_improvements": [
    {
      "change": "Reduce notice period: 90d → 15d",
      "rank_improvement": 18,
      "score_delta": 0.041200,
      "feasibility": "Negotiable with current employer"
    },
    {
      "change": "Mark profile as Open to Work",
      "rank_improvement": 6,
      "score_delta": 0.013400,
      "feasibility": "Can do immediately"
    },
    {
      "change": "Improve recruiter response rate: 12% → 85%",
      "rank_improvement": 3,
      "score_delta": 0.007800,
      "feasibility": "Respond to recruiter messages promptly"
    }
  ],
  "summary": "With key changes, candidate could reach approximately rank #23 (currently #47)."
}
```

---

## 7. Integration Quick-Start for Member 3

### Step 1 — Check server is up

```typescript
const res = await axios.get(`${API_URL}/api/health`);
if (res.data.status !== 'ok') throw new Error('Backend not ready');
```

### Step 2 — Load rankings

```typescript
const res = await axios.post(`${API_URL}/api/rank`, {
  candidates: candidatesArray,   // array of raw candidate objects
  include_counterfactual: false
});
const ranked = res.data.results;  // RankedCandidateItem[]
```

For the demo mode with 50 pre-loaded candidates, pass them in the request body.

### Step 3 — Candidate detail page

```typescript
const res = await axios.get(`${API_URL}/api/candidate/${candidateId}`);
const detail = res.data;  // CandidateDetailResponse
```

### Step 4 — Compare page

```typescript
const res = await axios.post(`${API_URL}/api/compare`, {
  candidate_a_id: idA,
  candidate_b_id: idB
});
const comparison = res.data;  // CompareResponse
```

### Step 5 — Analytics page

```typescript
const res = await axios.get(`${API_URL}/api/stats`);
const stats = res.data;  // StatsResponse
```

### Score display conventions

| Value | Display |
|---|---|
| `final_score` (0–1) | Multiply by 100 for percentage display |
| `capability`, `trajectory`, `recruitability`, `authenticity` (0–100) | Display as-is with progress bars |
| `confidence.label` | `"High"` → green badge, `"Medium"` → yellow, `"Low"` → grey |
| `career_dna` | `"Startup Builder"` → green, `"Scale Expert"` → blue, `"Product Engineer"` → teal, `"Research Specialist"` → orange, `"Consulting Only"` → red |
| `authenticity.flags` non-empty | Show orange warning on candidate card |

### Error handling

All error responses follow FastAPI's default format:

```json
{ "detail": "Human-readable error message" }
```

Handle 404 (candidate not in pool) and 503 (distributions not loaded) gracefully in the UI rather than showing a blank screen.
