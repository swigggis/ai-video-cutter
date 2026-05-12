from __future__ import annotations

import json
import logging
from pathlib import Path

from ..config import settings
from ..job_store import job_store
from ..schemas import Segment
from .ffmpeg_service import cut_and_concat, normalize_to_mp4, probe_duration, sanitize_segments
from .llm_service import extract_highlights
from .whisper_service import transcribe_video


logger = logging.getLogger(__name__)


def _update(job_id: str, *, progress: int, message: str, status: str = "processing") -> None:
    job_store.update(job_id, progress=progress, message=message, status=status)


def run_pipeline(job_id: str, source_file: Path, language: str, user_prompt: str | None) -> None:
    try:
        _update(job_id, progress=5, message="Validating and converting input video")
        processing_input = normalize_to_mp4(source_file, source_file.with_suffix(".mp4"))

        _update(job_id, progress=30, message="Running Whisper transcription on GPU/CPU")
        transcript_segments = transcribe_video(str(processing_input), language)
        transcript_path = settings.outputs_dir / f"{source_file.stem}_{job_id}_transcript.json"
        transcript_path.write_text(
            json.dumps([segment.model_dump() for segment in transcript_segments], indent=2),
            encoding="utf-8",
        )

        _update(job_id, progress=60, message="Sending transcript to LM Studio for highlight detection")
        llm_segments = extract_highlights(transcript_segments, user_prompt)

        duration = probe_duration(processing_input)
        safe_segments: list[Segment] = sanitize_segments(llm_segments, duration)
        if not safe_segments:
            safe_segments = sanitize_segments(transcript_segments, duration)

        highlight_path = settings.outputs_dir / f"{source_file.stem}_{job_id}_highlights.json"
        highlight_path.write_text(
            json.dumps([segment.model_dump() for segment in safe_segments], indent=2),
            encoding="utf-8",
        )

        _update(job_id, progress=85, message="Cutting and concatenating final video with ffmpeg")
        output_name = f"{source_file.stem}_{job_id}{source_file.suffix.lower()}"
        output_path = settings.outputs_dir / output_name
        cut_and_concat(processing_input, output_path, safe_segments)

        job_store.update(
            job_id,
            status="completed",
            progress=100,
            message="Processing completed",
            output_filename=output_name,
        )
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", job_id)
        job_store.update(
            job_id,
            status="failed",
            progress=100,
            message="Processing failed",
            error=str(exc),
        )
