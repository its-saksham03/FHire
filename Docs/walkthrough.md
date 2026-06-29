# Walkthrough - Production Readiness & FHire Branding Hardening

This walkthrough documents the updates made to transition the project from a hackathon demo to a production-grade, deployment-ready web service named **FHire**.

---

## 1. Product Rebranding (Rename to FHire)

We completed a codebase-wide search and replace to transition all user-facing branding text from **TalentGraph X** to **FHire**.

### Changes Made:
* Updated Navbar logo text to `FHire` (removed the styled `X` suffix to match the new brand identity).
* Replaced all display strings, metadata fields, browser titles, and console logging statements across **40 files** (including `layout.tsx`, `intake/page.tsx`, `api.ts`, environment variables, route handler docstrings, and markdown docs).
* Verified that all Next.js TSX builds and Python compilers completed cleanly.

---

## 2. Automated Asset Acquisition (Google Drive Downloader)

Previously, two large pre-computed data files (`data/candidates.jsonl` ~465MB and `data/embeddings.npz` ~136MB) had to be manually placed in the repository. We designed a startup lifespan hook that handles this dynamically.

### How it Works:
1. **Startup Check**: On boot, `lifespan` in `main.py` checks for the existence and validity of both files.
2. **Warning Bypassing**: Since these files exceed Google Drive's virus scan limit, the script parses the form parameters (`confirm`, `uuid`) from Google's warning HTML pages and resubmits them to the usercontent endpoint.
3. **Chunked Streaming & Progress Logs**: Downloads are streamed in 1MB chunks directly to disk with status progress logs written to the console.
4. **Integrity Validation**: Once downloaded, the script validates that:
   * `candidates.jsonl` contains valid JSON records.
   * `embeddings.npz` can be loaded successfully by `numpy` and contains the required arrays (`jd`, `candidates`).
5. **SSL Verification Fallback**: SSL warnings are disabled via `urllib3` if a connection fails due to local issuer verification issues on standard corporate Proxies/VPNs.

---

## 3. Reliability and Cloud Deployment (Render Integration)

To make the service production-ready on cloud providers like Render, several server-level improvements were made:

1. **GET `/` and `/health` Endpoints**:
   * Mounted `/` and `/health` endpoints outside of the `/api` prefix.
   * `/health` returns the server status (`ok`), service name, and version (`4.0`), allowing Render to track deployment health during boot-up.
2. **Dynamic Port Binding**:
   * The entry point dynamically binds the server to the `PORT` environment variable assigned by the hosting environment.
3. **Exponential Retry Logic**:
   * Added `requests_get_with_retry` wrapping all download calls. It performs up to 3 attempts with an exponential backoff of `2 ** attempt` seconds, guaranteeing the server startup never hangs indefinitely on transient network drops.

---

## 4. Verification & Output Logs

An automated testing script launched the FastAPI server, verified the entire startup order (Asset Check → Asset Verification → Load Distributions → Load Candidates → Load Embeddings → Build Indexes → Startup Ranking → Accept Requests), and successfully queried the root and health endpoints:

```text
Launching backend server...
Waiting for server startup to complete (polling GET /health)...
  Server is not ready yet, retrying in 3 seconds...
  ...
Server is up and running after 45.0 seconds!
Testing GET / ...
Response / : {'service': 'FHire Backend', 'status': 'running'}
Testing GET /health ...
Response /health : {'status': 'ok', 'service': 'FHire Backend', 'version': '4.0'}

[SUCCESS] Health check and root endpoints verified successfully!
Stopping backend server...
```
The server also demonstrated clean shutdown behavior under `SIGTERM` signals.
