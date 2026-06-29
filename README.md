# FHire — AI Recruiter Intelligence Engine

FHire is a production-grade candidate ranking dashboard. It evaluates candidates using a four-dimensional scoring model combined with a job intake requirement matching engine.

## Automatic Backend Asset Download

To run the backend, two large pre-computed data files are required:
* `data/candidates.jsonl` (approx. 487 MB)
* `data/embeddings.npz` (approx. 142 MB)

These files are hosted on Google Drive. **On the first startup of the backend, the system will automatically detect if these files are missing and download them.**

### How it works
1. When you run `uvicorn backend.main:app` or start the FastAPI application, a lifespan startup check executes.
2. The module `backend/utils/download_assets.py` checks for the existence of `data/candidates.jsonl` and `data/embeddings.npz` in the Backend project root.
3. If either file is missing or corrupted:
   * It creates the `Backend/data/` folder if it is missing.
   * It contacts Google Drive and handles the download virus scan confirmation mechanism using Python's standard `requests` library.
   * It prints real-time download progress in the terminal (showing size and download rate).
   * It performs an integrity verification pass after download, verifying that the candidates file is valid JSONL format and that the NPZ file can be loaded correctly via `numpy`.
4. If both files are verified, the startup process completes successfully and the FastAPI server starts.

---

## Running the Backend

1. Navigate to the `Backend` directory:
   ```bash
   cd Backend
   ```
2. Install the required Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Start the FastAPI server:
   ```bash
   python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
   ```

*Note: The first execution will take some time as it downloads the 600+ MB dataset.*
