from __future__ import annotations

import logging
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import ensure_runtime_directories, settings
from .job_store import job_store
from .logging_config import configure_logging
from .schemas import JobResponse
from .services.ffmpeg_service import VIDEO_EXTENSIONS
from .services.pipeline_service import run_pipeline
from .services.whisper_service import resolve_device


ensure_runtime_directories()
configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI(title="Automated AI Video Cutter", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _job_to_response(job_id: str) -> JobResponse:
    state = job_store.get(job_id)
    if not state:
        raise HTTPException(status_code=404, detail="Job not found")
    download_url = f"/api/jobs/{job_id}/download" if state.output_filename else None
    return JobResponse(
        job_id=job_id,
        status=state.status,
        progress=state.progress,
        message=state.error or state.message,
        download_url=download_url,
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    device, compute_type = resolve_device()
    return {
        "status": "ok",
        "whisper_device": device,
        "whisper_compute_type": compute_type,
        "lmstudio_model": settings.lmstudio_model,
    }


@app.post("/api/jobs", response_model=JobResponse)
async def create_job(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    language: str = Form("de"),
    user_prompt: str = Form(""),
) -> JobResponse:
    extension = Path(file.filename or "").suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        raise HTTPException(status_code=400, detail=f"Unsupported file extension: {extension}")
    if language not in {"de", "en"}:
        raise HTTPException(status_code=400, detail="Language must be 'de' or 'en'")

    job_id = str(uuid4())
    job_store.create(job_id)

    safe_name = Path(file.filename or f"upload_{job_id}{extension}").name
    source_path = settings.uploads_dir / f"{job_id}_{safe_name}"

    try:
        contents = await file.read()
        source_path.write_bytes(contents)
    except Exception as exc:
        logger.exception("Upload failed for job %s", job_id)
        raise HTTPException(status_code=500, detail=f"Could not save file: {exc}") from exc

    background_tasks.add_task(run_pipeline, job_id, source_path, language, user_prompt)
    return _job_to_response(job_id)


@app.get("/api/jobs/{job_id}", response_model=JobResponse)
def get_job(job_id: str) -> JobResponse:
    return _job_to_response(job_id)


@app.get("/api/jobs/{job_id}/download")
def download_job_output(job_id: str) -> FileResponse:
    state = job_store.get(job_id)
    if not state or not state.output_filename:
        raise HTTPException(status_code=404, detail="Output not available")
    output_path = settings.outputs_dir / state.output_filename
    if not output_path.exists():
        raise HTTPException(status_code=404, detail="Output file missing")
    return FileResponse(path=output_path, filename=output_path.name)
