import sys, json
sys.path.insert(0, '.')

from core.disqualifier import is_disqualified
from core.capability_engine import capability_score, career_evidence_score
from core.trajectory_engine import trajectory_score_final

# Load a few sample candidates
sample_path = r'C:\Users\LAKSHYA ANAND\Desktop\IndiaRuns Hack\[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\[PUB] India_runs_data_and_ai_challenge\India_runs_data_and_ai_challenge\sample_candidates.json'
with open(sample_path) as f:
    samples = json.load(f)

print('Testing on sample_candidates.json...')
print('='*60)

passed = 0
disqualified = 0

for c in samples[:30]:
    cid = c["candidate_id"]
    title = c["profile"]["current_title"]
    disq, reason = is_disqualified(c)
    if disq:
        disqualified += 1
        print("  DISQ: " + cid + " | " + title + " | " + str(reason))
    else:
        passed += 1
        cap = capability_score(c, 50.0)
        traj = trajectory_score_final(c)
        print("  PASS: " + cid + " | " + title[:30].ljust(30) + " | cap=" + str(round(cap,1)) + " | traj=" + str(round(traj["score"],1)) + " | dna=" + traj["dna"])

print()
print("Results: " + str(passed) + " passed, " + str(disqualified) + " disqualified out of 30 tested")
