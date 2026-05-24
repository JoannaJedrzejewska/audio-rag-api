from __future__ import annotations
from enum import Enum
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class JobStatus(str, Enum):
    queued     = "queued"
    processing = "processing"
    completed  = "completed"
    failed     = "failed"


#Audio

class TranscribeResponse(BaseModel):
    job_id:  str
    status:  JobStatus
    message: str


class JobStatusResponse(BaseModel):
    job_id:        str
    status:        JobStatus
    filename:      str
    created_at:    datetime
    transcription: Optional[str] = None
    error:         Optional[str] = None


#RAG

class SearchRequest(BaseModel):
    query:  str   = Field(..., min_length=2, max_length=500)
    top_k:  int   = Field(default=5, ge=1, le=20)


class SearchResultItem(BaseModel):
    job_id:        str
    filename:      str
    transcription: str
    score:         float = Field(..., ge=0.0, le=1.0)
    created_at:    Optional[str] = None


class SearchResponse(BaseModel):
    query:       str
    results:     list[SearchResultItem]
    total_found: int


class AnswerRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    top_k:    int = Field(default=5, ge=1, le=20)


class AnswerSource(BaseModel):
    job_id:   str
    filename: str
    excerpt:  str


class AnswerResponse(BaseModel):
    question:   str
    answer:     str
    sources:    list[AnswerSource]
    model_used: str


#Health

class HealthResponse(BaseModel):
    status:     str
    version:    str
    components: dict[str, str]
