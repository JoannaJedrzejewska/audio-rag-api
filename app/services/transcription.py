import asyncio
import uuid
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Optional
from faster_whisper import WhisperModel
from app.core.config import settings

_jobs: dict = {}
_model = None

def load_model():
    global _model
    if _model is None:
        _model = WhisperModel(settings.whisper_model, device="cpu", compute_type="int8")
    return _model

def create_job(filename: str) -> str:
    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id": job_id, "status": "queued", "filename": filename,
        "transcription": None, "error": None, "created_at": datetime.utcnow(),
    }
    return job_id

def get_job(job_id: str):
    return _jobs.get(job_id)

def _transcribe_sync(job_id: str, audio_bytes: bytes, filename: str) -> None:
    job = _jobs[job_id]
    tmp_path = None
    try:
        job["status"] = "processing"
        suffix = Path(filename).suffix or ".wav"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(audio_bytes)
            tmp_path = tmp.name
        model = load_model()
        segments, info = model.transcribe(tmp_path, beam_size=5, vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments)
        job["status"] = "completed"
        job["transcription"] = text
        job["language"] = info.language
        from app.services.vector_store import add_document
        add_document(job_id, text, {"job_id": job_id, "filename": filename,
                                    "created_at": datetime.utcnow().isoformat()})
    except Exception as e:
        job["status"] = "failed"
        job["error"] = str(e)
    finally:
        if tmp_path:
            Path(tmp_path).unlink(missing_ok=True)

async def run_transcription(job_id: str, audio_bytes: bytes, filename: str) -> None:
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _transcribe_sync, job_id, audio_bytes, filename)
