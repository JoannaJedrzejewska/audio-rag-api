import argparse
import json
import time
from pathlib import Path

import requests


API_BASE = "http://127.0.0.1:8000"
POLL_INTERVAL = 5
MAX_WAIT_SEC = 3600
MAX_CONNECTION_ERRORS = 24


def upload_file(path: Path, api_base: str) -> dict:
    with path.open("rb") as file_handle:
        response = requests.post(
            f"{api_base}/audio/transcribe",
            files={"file": (path.name, file_handle, "audio/wav")},
            timeout=600,
        )

    response.raise_for_status()
    return response.json()


def wait_for_job(job_id: str, api_base: str) -> dict:
    elapsed = 0
    connection_errors = 0

    while elapsed < MAX_WAIT_SEC:
        try:
            response = requests.get(
                f"{api_base}/audio/jobs/{job_id}",
                timeout=15,
            )
            response.raise_for_status()
            job = response.json()
            connection_errors = 0

            if job["status"] in {"completed", "failed"}:
                return job

        except requests.RequestException as error:
            connection_errors += 1
            print(
                f"\n  API temporarily unavailable "
                f"({connection_errors}/{MAX_CONNECTION_ERRORS}): {error}",
                flush=True,
            )

            if connection_errors >= MAX_CONNECTION_ERRORS:
                return {
                    "job_id": job_id,
                    "status": "connection_error",
                    "error": str(error),
                }

        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL

    return {
        "job_id": job_id,
        "status": "timeout",
        "error": f"Job did not complete within {MAX_WAIT_SEC} seconds.",
    }


def save_results(results: list[dict], output_path: Path) -> None:
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    with temporary_path.open("w", encoding="utf-8") as file_handle:
        json.dump(results, file_handle, ensure_ascii=False, indent=2)

    temporary_path.replace(output_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Upload audio files to Audio RAG API and wait for transcription jobs."
    )
    parser.add_argument("--input", required=True, help="Folder containing audio files")
    parser.add_argument("--ext", default="wav", help="Extension: wav, mp3, m4a, mp4")
    parser.add_argument(
        "--api",
        default=API_BASE,
        help="API base URL, e.g. http://127.0.0.1:8000",
    )
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--results", default="upload_results.json")
    args = parser.parse_args()

    input_directory = Path(args.input)
    output_path = Path(args.results)
    extension = args.ext.lower().lstrip(".")
    files = sorted(input_directory.glob(f"*.{extension}"))

    if args.limit is not None:
        files = files[:args.limit]

    if not files:
        print(f"No *.{extension} files found in {input_directory}")
        return

    try:
        health_response = requests.get(f"{args.api}/health", timeout=15)
        health_response.raise_for_status()
    except requests.RequestException as error:
        raise SystemExit(f"API is unavailable at {args.api}: {error}")

    print(f"Uploading {len(files)} file(s) to {args.api}\n")
    results: list[dict] = []

    for index, path in enumerate(files, start=1):
        print(f"[{index}/{len(files)}] {path.name}", flush=True)

        try:
            job = upload_file(path, args.api)
            job_id = job["job_id"]
            print(f"  Accepted: job_id={job_id}", flush=True)

            final = wait_for_job(job_id, args.api)
            print(f"  Result: {final['status']}", flush=True)
            results.append({"file": path.name, **final})

        except requests.RequestException as error:
            print(f"  Upload error: {error}", flush=True)
            results.append(
                {
                    "file": path.name,
                    "status": "upload_error",
                    "error": str(error),
                }
            )

        save_results(results, output_path)

    completed = sum(item["status"] == "completed" for item in results)
    print(f"\nCompleted: {completed}/{len(files)}")
    print(f"Results: {output_path}")


if __name__ == "__main__":
    main()
