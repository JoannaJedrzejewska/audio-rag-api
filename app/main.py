import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from app.core.config import settings
from app.routers.audio import router as audio_router
from app.routers.rag   import router as rag_router
from app.schemas.models import HealthResponse


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.transcription import load_model as wm
    from app.services.embeddings    import load_model as em
    from app.services.vector_store  import get_collection
    wm(); em(); get_collection()
    logger.info("API gotowe.")
    yield


app = FastAPI(title="Audio RAG API", version=settings.version, lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])
app.include_router(audio_router)
app.include_router(rag_router)


@app.get("/health", response_model=HealthResponse, tags=["health"])
def health():
    from app.services.transcription import _model as wm
    from app.services.embeddings    import _model as em
    from app.services.vector_store  import chromadb_status
    return HealthResponse(status="ok", version=settings.version, components={
        "api": "ok", "chromadb": chromadb_status(),
        "whisper": "loaded" if wm else "not loaded",
        "embeddings": "loaded" if em else "not loaded",
        "llm": settings.llm_provider,
    })