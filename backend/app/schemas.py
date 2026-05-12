from __future__ import annotations

from pydantic import BaseModel, Field


class Segment(BaseModel):
    start: float = Field(..., ge=0)
    end: float = Field(..., ge=0)
    text: str = ""


class JobResponse(BaseModel):
    job_id: str
    status: str
    progress: int
    message: str
    download_url: str | None = None
