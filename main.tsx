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


def _is_cuda_oom(error: Exception) -> bool:
    message = str(error).lower()
    return "out of memory" in message or "cuda failed" in message


def _build_load_attempts() -> list[tuple[str, str, str]]:
    base_device, base_compute_type = resolve_device()
    attempts: list[tuple[str, str, str]] = [(settings.whisper_model, base_device, base_compute_type)]

    if base_device == "cuda":
        attempts.append((settings.whisper_model, "cuda", "int8_float16"))
        if settings.whisper_fallback_model and settings.whisper_fallback_model != settings.whisper_model:
            attempts.append((settings.whisper_fallback_model, "cuda", "float16"))
            attempts.append((settings.whisper_fallback_model, "cuda", "int8_float16"))
        if settings.enable_cpu_fallback:
            attempts.append((settings.whisper_model, "cpu", "int8"))
            if settings.whisper_fallback_model and settings.whisper_fallback_model != settings.whisper_model:
                attempts.append((settings.whisper_fallback_model, "cpu", "int8"))

    # Keep order but drop duplicates.
    return list(dict.fromkeys(attempts))


@lru_cache(maxsize=1)
def get_model() -> WhisperModel:
    last_error: Exception | None = None

    for model_name, device, compute_type in _build_load_attempts():
        try:
            logger.info("Loading Whisper model '%s' on device=%s compute_type=%s", model_name, device, compute_type)
            return WhisperModel(
                model_name,
                device=device,
                compute_type=compute_type,
                download_root=str(settings.models_dir),
            )
        except Exception as exc:  # pragma: no cover - runtime environment dependent
            last_error = exc
            if _is_cuda_oom(exc):
                logger.warning(
                    "Whisper model load failed with CUDA OOM for model=%s compute_type=%s. Trying fallback.",
                    model_name,
                    compute_type,
                )
                continue
            logger.exception("Whisper model load failed")
            raise

    raise RuntimeError("Could not load any Whisper model fallback") from last_error


def warmup_model() -> None:
    # First run may download multiple GB from Hugging Face.
    get_model()


def transcribe_video(input_file: str, language: str) -> list[Segment]:
    model = get_model()
    language_code = "de" if language == "de" else "en"

    segments, info = model.transcribe(
        input_file,
        language=language_code,
        beam_size=settings.whisper_beam_size,
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
