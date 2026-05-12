from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")


@dataclass(frozen=True)
class Settings:
    backend_host: str = os.getenv("BACKEND_HOST", "0.0.0.0")
    backend_port: int = int(os.getenv("BACKEND_PORT", "8000"))
    frontend_origin: str = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")

    uploads_dir: Path = BASE_DIR / os.getenv("UPLOADS_DIR", "uploads")
    outputs_dir: Path = BASE_DIR / os.getenv("OUTPUTS_DIR", "outputs")
    logs_dir: Path = BASE_DIR / os.getenv("LOGS_DIR", "logs")
    models_dir: Path = BASE_DIR / os.getenv("MODELS_DIR", "models")

    whisper_model: str = os.getenv("WHISPER_MODEL", "large-v3")
    whisper_device: str = os.getenv("WHISPER_DEVICE", "auto")
    whisper_compute_type: str = os.getenv("WHISPER_COMPUTE_TYPE", "float16")

    lmstudio_base_url: str = os.getenv("LMSTUDIO_BASE_URL", "http://127.0.0.1:1234/v1")
    lmstudio_model: str = os.getenv("LMSTUDIO_MODEL", "qwen/qwen3.5-9b")
    lmstudio_timeout_seconds: int = int(os.getenv("LMSTUDIO_TIMEOUT_SECONDS", "120"))

    enable_cpu_fallback: bool = os.getenv("ENABLE_CPU_FALLBACK", "true").lower() == "true"
    ffmpeg_bin: str = os.getenv("FFMPEG_BIN", "ffmpeg")
    ffprobe_bin: str = os.getenv("FFPROBE_BIN", "ffprobe")


settings = Settings()


def ensure_runtime_directories() -> None:
    for directory in [settings.uploads_dir, settings.outputs_dir, settings.logs_dir, settings.models_dir]:
        directory.mkdir(parents=True, exist_ok=True)
