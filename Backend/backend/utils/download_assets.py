import os
import sys
import time
import requests
import json
import re
import numpy as np
from pathlib import Path
import urllib3

# Disable urllib3 SSL warnings for security verification bypass
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Google Drive File IDs
CANDIDATES_FILE_ID = "16x00zg7cQ5TrKlaBXJIUxYjpIxRHBJ96"
EMBEDDINGS_FILE_ID = "1vfeYPTtk7I3YxUcyKr8Ju19Im2wlJvpR"

# Resolve absolute Backend root folder
BACKEND_ROOT = Path(__file__).resolve().parent.parent.parent

def find_input_value(name: str, html: str) -> str:
    # Match input tags with name and value attributes in any order
    pattern1 = rf'name="{name}"\s+value="([^"]+)"'
    pattern2 = rf'value="([^"]+)"\s+name="{name}"'
    
    match = re.search(pattern1, html, re.IGNORECASE)
    if match:
        return match.group(1)
        
    match = re.search(pattern2, html, re.IGNORECASE)
    if match:
        return match.group(1)
        
    return None

def requests_get_with_retry(session: requests.Session, url: str, params: dict, stream: bool = True, timeout: int = 15) -> requests.Response:
    max_attempts = 3
    backoff_factor = 2
    for attempt in range(1, max_attempts + 1):
        try:
            response = session.get(url, params=params, stream=stream, timeout=timeout, verify=False)
            response.raise_for_status()
            return response
        except (requests.exceptions.RequestException, Exception) as e:
            print(f"  [Warning] Attempt {attempt} failed: {e}")
            if attempt == max_attempts:
                print(f"  [Error] Max download attempts (3) exceeded for URL: {url}")
                raise
            sleep_time = backoff_factor ** attempt
            print(f"  Retrying in {sleep_time} seconds...")
            time.sleep(sleep_time)

def download_file_from_google_drive(file_id: str, destination: Path):
    url = "https://docs.google.com/uc?export=download"
    session = requests.Session()

    print(f"Connecting to Google Drive to download File ID: {file_id}...")
    try:
        response = requests_get_with_retry(session, url, {'id': file_id}, stream=True, timeout=20)
    except Exception as e:
        raise RuntimeError(f"Connection to Google Drive failed after 3 attempts: {e}")

    # Check cookies first
    token = None
    for key, value in response.cookies.items():
        if key.startswith('download_warning'):
            token = value
            break

    # Check if we received the HTML virus scan warning page
    content_type = response.headers.get('content-type', '')
    if not token and 'text/html' in content_type:
        # Download the HTML content to parse hidden input fields
        html_content = response.text
        confirm_val = find_input_value("confirm", html_content)
        uuid_val = find_input_value("uuid", html_content)
        
        if confirm_val:
            # Re-request using drive.usercontent.google.com/download which hosts the actual download endpoint
            dl_url = "https://drive.usercontent.google.com/download"
            params = {
                'id': file_id,
                'export': 'download',
                'confirm': confirm_val
            }
            if uuid_val:
                params['uuid'] = uuid_val
                
            print("  Warning page detected. Resubmitting confirmation token...")
            try:
                response = requests_get_with_retry(session, dl_url, params, stream=True, timeout=30)
            except Exception as e:
                raise RuntimeError(f"Download request failed after 3 attempts: {e}")
        else:
            # Fallback to confirm=t
            print("  Warning page detected. Using confirm=t fallback...")
            params = {'id': file_id, 'confirm': 't'}
            try:
                response = requests_get_with_retry(session, url, params, stream=True, timeout=30)
            except Exception as e:
                raise RuntimeError(f"Download request failed after 3 attempts: {e}")
    elif token:
        # Re-request docs.google.com/uc with warning token from cookie
        params = {'id': file_id, 'confirm': token}
        try:
            response = requests_get_with_retry(session, url, params, stream=True, timeout=30)
        except Exception as e:
            raise RuntimeError(f"Download request failed after 3 attempts: {e}")

    try:
        response.raise_for_status()
    except Exception as e:
        raise RuntimeError(f"Google Drive HTTP error: {e}")

    # Check content length header if provided
    total_size = response.headers.get('content-length')
    if total_size:
        total_size = int(total_size)
        print(f"  Asset size: {total_size / (1024 * 1024):.2f} MB")
    else:
        print("  Content-Length header not provided. Streaming download...")

    chunk_size = 1024 * 1024  # 1MB buffer
    bytes_downloaded = 0
    start_time = time.time()
    last_log_time = start_time

    print(f"  Streaming data directly to: {destination}")
    with open(destination, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                f.write(chunk)
                bytes_downloaded += len(chunk)
                
                # Log progress periodically to avoid logging spam but keep user updated
                current_time = time.time()
                if current_time - last_log_time >= 3:
                    elapsed = current_time - start_time
                    speed = (bytes_downloaded / (1024 * 1024)) / elapsed if elapsed > 0 else 0
                    if total_size:
                        pct = (bytes_downloaded / total_size) * 100
                        print(f"    Downloaded {bytes_downloaded / (1024*1024):.1f} MB / {total_size / (1024*1024):.1f} MB ({pct:.1f}%) @ {speed:.2f} MB/s")
                    else:
                        print(f"    Downloaded {bytes_downloaded / (1024*1024):.1f} MB @ {speed:.2f} MB/s")
                    last_log_time = current_time

    duration = time.time() - start_time
    avg_speed = (bytes_downloaded / (1024 * 1024)) / duration if duration > 0 else 0
    print(f"  Download completed: {bytes_downloaded / (1024*1024):.1f} MB in {duration:.1f}s (Average Speed: {avg_speed:.2f} MB/s)")
    return bytes_downloaded

def verify_candidates_file(path: Path):
    print(f"Verifying integrity of candidates dataset: {path}")
    if not path.exists():
        raise ValueError(f"Candidates file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Candidates file is empty: {path}")
    
    # Check if file has valid JSON structure on the first line
    with open(path, "r", encoding="utf-8") as f:
        line = f.readline()
        if not line:
            raise ValueError(f"Candidates file is empty: {path}")
        try:
            data = json.loads(line)
            if "candidate_id" not in data:
                raise ValueError("Dataset JSON format is incorrect (missing 'candidate_id').")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSONL formatting in candidates dataset: {e}")
    print("  [OK] Candidates dataset verified successfully.")

def verify_embeddings_file(path: Path):
    print(f"Verifying integrity of pre-computed embeddings: {path}")
    if not path.exists():
        raise ValueError(f"Embeddings file does not exist: {path}")
    if path.stat().st_size == 0:
        raise ValueError(f"Embeddings file is empty: {path}")
        
    try:
        with np.load(path) as data:
            if "jd" not in data or "candidates" not in data:
                raise ValueError("NPZ file is missing required arrays: 'jd' and/or 'candidates'")
    except Exception as e:
        raise ValueError(f"Failed to load NPZ embeddings file: {e}")
    print("  [OK] Pre-computed embeddings verified successfully.")

def check_and_download_all_assets():
    """
    Checks if candidates.jsonl and embeddings.npz exist.
    If missing, downloads them from Google Drive and runs integrity checks.
    """
    candidates_env = os.environ.get("CANDIDATES_PATH")
    if candidates_env:
        candidates_path = Path(candidates_env)
    else:
        candidates_path = BACKEND_ROOT / "data" / "candidates.jsonl"

    embeddings_env = os.environ.get("EMBEDDINGS_PATH")
    if embeddings_env:
        embeddings_path = Path(embeddings_env)
    else:
        embeddings_path = BACKEND_ROOT / "data" / "embeddings.npz"

    # Verify or download Candidates File
    candidates_missing = not candidates_path.exists()
    if candidates_missing:
        print(f"\n[Asset Check] Candidates dataset is missing at: {candidates_path}")
    else:
        try:
            verify_candidates_file(candidates_path)
        except Exception as e:
            print(f"\n[Asset Check] Candidates dataset verification failed: {e}")
            candidates_missing = True

    if candidates_missing:
        # Create parent directory if needed
        candidates_path.parent.mkdir(parents=True, exist_ok=True)
        print("Starting candidates dataset download...")
        try:
            download_file_from_google_drive(CANDIDATES_FILE_ID, candidates_path)
            verify_candidates_file(candidates_path)
        except Exception as e:
            print(f"\nCRITICAL ERROR: Failed to obtain candidates dataset: {e}", file=sys.stderr)
            sys.exit(1)

    # Verify or download Embeddings File
    embeddings_missing = not embeddings_path.exists()
    if embeddings_missing:
        print(f"\n[Asset Check] Embeddings NPZ file is missing at: {embeddings_path}")
    else:
        try:
            verify_embeddings_file(embeddings_path)
        except Exception as e:
            print(f"\n[Asset Check] Embeddings NPZ verification failed: {e}")
            embeddings_missing = True

    if embeddings_missing:
        # Create parent directory if needed
        embeddings_path.parent.mkdir(parents=True, exist_ok=True)
        print("Starting embeddings download...")
        try:
            download_file_from_google_drive(EMBEDDINGS_FILE_ID, embeddings_path)
            verify_embeddings_file(embeddings_path)
        except Exception as e:
            print(f"\nCRITICAL ERROR: Failed to obtain embeddings: {e}", file=sys.stderr)
            sys.exit(1)

    print("\n[Asset Check] All backend assets are present and verified.")

if __name__ == "__main__":
    check_and_download_all_assets()
