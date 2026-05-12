from __future__ import annotations

import logging
from functools import lru_cache

from faster_whisper import WhisperModel

from ..config import settings
from ..schemas import Segment


logger = logging.getLogger(__name__)


def _torch_cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def resolve_device() -> tuple[str, str]:
    if settings.whisper_device in {"cuda", "cpu"}:
        return settings.whisper_device, settings.whisper_compute_type

    if _torch_cuda_available():
        return "cuda", settings.whisper_compute_type

    if settings.enable_cpu_fallback:
        return "cpu", "int8"

    raise RuntimeError("CUDA device not available and CPU fallback is disabled")


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    device, compute_type = resolve_device()
    logger.info("Loading Whisper model '%s' on device=%s compute_type=%s", settings.whisper_model, device, compute_type)
    return WhisperModel(
        settings.whisper_model,
        device=device,
        compute_type=compute_type,
        download_root=str(settings.models_dir),
    )


def warmup_model() -> None:
    # First run may download multiple GB from Hugging Face.
    get_model()


def transcribe_video(input_file: str, language: str) -> list[Segment]:
    model = get_model()
    language_code = "de" if language == "de" else "en"

    segments, info = model.transcribe(
        input_file,
        language=language_code,
        beam_size=5,
        vad_filter=True,
    )
    logger.info("Transcription finished language=%s duration=%s", info.language, info.duration)

    return [
        Segment(
            start=round(segment.start, 3),
            end=round(segment.end, 3),
            text=segment.text.strip(),
        )
        for segment in segments
    ]
