import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks, status
from pathlib import Path

from app.core.config import settings
from app.schemas.models import TranscribeResponse, JobStatusResponse, JobStatus
from app.services import transcription as svc

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/audio", tags=["audio"])

ALLOWED_SUFFIXES   = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".mp4", ".webm"}
ALLOWED_MIMETYPES  = {
    "audio/wav", "audio/mpeg", "audio/flac", "audio/ogg",
    "audio/mp4", "audio/x-m4a", "video/mp4", "video/webm",
}


@router.post(
    "/transcribe",
    response_model=TranscribeResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Prześlij plik audio do transkrypcji",
)
async def transcribe_audio(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
):
    suffix = Path(file.filename or "").suffix.lower()
    mime   = (file.content_type or "").split(";")[0].strip().lower()

    if suffix not in ALLOWED_SUFFIXES and mime not in ALLOWED_MIMETYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Nieobsługiwany format pliku '{suffix}'. "
                f"Dozwolone: {', '.join(sorted(ALLOWED_SUFFIXES))}"
            ),
        )

    audio_bytes = await file.read()

    max_bytes = settings.max_file_size_mb * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Plik za duży. Maksymalny rozmiar: {settings.max_file_size_mb} MB.",
        )

    if len(audio_bytes) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Plik jest pusty.",
        )

    job_id = svc.create_job(file.filename or "audio.wav")
    background_tasks.add_task(
        svc.run_transcription,
        job_id,
        audio_bytes,
        file.filename or "audio.wav",
    )

    return TranscribeResponse(
        job_id=job_id,
        status=JobStatus.queued,
        message="Zadanie transkrypcji zostało przyjęte.",
    )


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    summary="Sprawdź status zadania transkrypcji",
)
def get_job_status(job_id: str):
    job = svc.get_job(job_id)
    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Zadanie '{job_id}' nie istnieje.",
        )
    return JobStatusResponse(**job)
