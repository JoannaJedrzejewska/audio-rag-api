import time
import json
import argparse
from pathlib import Path

import requests

API_BASE    = "http://localhost:8000"
POLL_INTERVAL = 3
MAX_WAIT_SEC  = 3600


def upload_file(path: Path, api_base: str) -> dict:
    with open(path, "rb") as f:
        r = requests.post(
            f"{api_base}/audio/transcribe",
            files={"file": (path.name, f, "audio/wav")},
            timeout=600,
        )
    r.raise_for_status()
    return r.json()


def wait_for_job(job_id: str, api_base: str) -> dict:
    elapsed = 0
    while elapsed < MAX_WAIT_SEC:
        r = requests.get(f"{api_base}/audio/jobs/{job_id}", timeout=10)
        r.raise_for_status()
        job = r.json()
        if job["status"] in ("completed", "failed"):
            return job
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
    return {"status": "timeout", "job_id": job_id}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input",   required=True, help="Folder z plikami audio")
    parser.add_argument("--ext",     default="wav",  help="Rozszerzenie plików (wav/mp3/mp4)")
    parser.add_argument("--api",     default=API_BASE)
    parser.add_argument("--limit",   type=int, default=None)
    parser.add_argument("--results", default="upload_results.json")
    args = parser.parse_args()

    files = sorted(Path(args.input).glob(f"*.{args.ext}"))
    if args.limit:
        files = files[:args.limit]

    if not files:
        print(f"Brak plików *.{args.ext} w {args.input}")
        return

    print(f"Upload {len(files)} plików do {args.api}\n")

    results = []
    for i, path in enumerate(files, 1):
        print(f"[{i}/{len(files)}] {path.name} ... ", end="", flush=True)
        try:
            job = upload_file(path, args.api)
            job_id = job["job_id"]
            final  = wait_for_job(job_id, args.api)
            status = final["status"]
            icon   = "good" if status == "completed" else "not complete"
            print(f"{icon} {status}")
            results.append({"file": path.name, **final})
        except Exception as e:
            print(f"błąd: {e}")
            results.append({"file": path.name, "status": "error", "error": str(e)})

    with open(args.results, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    completed = sum(1 for r in results if r["status"] == "completed")
    print(f"\nZakończono: {completed}/{len(files)}")
    print(f"Wyniki: {args.results}")


if __name__ == "__main__":
    main()
