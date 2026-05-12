from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from ..config import settings
from ..schemas import Segment


logger = logging.getLogger(__name__)
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".m4v"}


def _run_ffmpeg(command: list[str]) -> None:
    logger.info("Running ffmpeg command: %s", " ".join(command))
    process = subprocess.run(command, capture_output=True, text=True)
    if process.returncode != 0:
        logger.error("ffmpeg failed: %s", process.stderr)
        raise RuntimeError(process.stderr.strip() or "ffmpeg execution failed")


def has_nvenc_support() -> bool:
    try:
        result = subprocess.run(
            [settings.ffmpeg_bin, "-hide_banner", "-encoders"],
            capture_output=True,
            text=True,
            check=False,
        )
        return "h264_nvenc" in result.stdout
    except Exception:  # pragma: no cover - runtime environment dependent
        return False


def probe_duration(input_path: Path) -> float:
    command = [
        settings.ffprobe_bin,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "json",
        str(input_path),
    ]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "ffprobe failed")
    payload = json.loads(result.stdout)
    return float(payload["format"]["duration"])


def normalize_to_mp4(input_path: Path, output_path: Path) -> Path:
    if input_path.suffix.lower() == ".mp4":
        return input_path

    encoder = "h264_nvenc" if has_nvenc_support() else "libx264"
    command = [
        settings.ffmpeg_bin,
        "-y",
        "-i",
        str(input_path),
        "-c:v",
        encoder,
        "-preset",
        "p4" if encoder == "h264_nvenc" else "medium",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_path),
    ]
    _run_ffmpeg(command)
    return output_path


def sanitize_segments(segments: list[Segment], duration: float) -> list[Segment]:
    sorted_segments = sorted(segments, key=lambda item: item.start)
    result: list[Segment] = []

    for item in sorted_segments:
        start = max(0.0, min(item.start, duration))
        end = max(0.0, min(item.end, duration))
        if end <= start:
            continue
        if result and start <= result[-1].end:
            result[-1].end = max(result[-1].end, end)
            result[-1].text = (result[-1].text + " " + item.text).strip()
            continue
        result.append(Segment(start=start, end=end, text=item.text))

    return result


def cut_and_concat(
    input_path: Path,
    requested_output_path: Path,
    segments: list[Segment],
) -> Path:
    if not segments:
        raise RuntimeError("No segments provided for cut")

    work_dir = requested_output_path.parent / f"tmp_{requested_output_path.stem}"
    work_dir.mkdir(parents=True, exist_ok=True)
    segment_files: list[Path] = []

    for index, segment in enumerate(segments):
        segment_file = work_dir / f"part_{index:04d}{input_path.suffix}"
        try:
            _run_ffmpeg(
                [
                    settings.ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{segment.start:.3f}",
                    "-to",
                    f"{segment.end:.3f}",
                    "-i",
                    str(input_path),
                    "-c",
                    "copy",
                    str(segment_file),
                ]
            )
        except RuntimeError:
            encoder = "h264_nvenc" if has_nvenc_support() else "libx264"
            _run_ffmpeg(
                [
                    settings.ffmpeg_bin,
                    "-y",
                    "-ss",
                    f"{segment.start:.3f}",
                    "-to",
                    f"{segment.end:.3f}",
                    "-i",
                    str(input_path),
                    "-c:v",
                    encoder,
                    "-preset",
                    "p4" if encoder == "h264_nvenc" else "medium",
                    "-c:a",
                    "aac",
                    str(segment_file),
                ]
            )

        segment_files.append(segment_file)

    concat_manifest = work_dir / "concat.txt"
    concat_manifest.write_text("\n".join([f"file '{path.as_posix()}'" for path in segment_files]), encoding="utf-8")

    merged_file = work_dir / f"merged{input_path.suffix}"
    try:
        _run_ffmpeg(
            [
                settings.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_manifest),
                "-c",
                "copy",
                str(merged_file),
            ]
        )
    except RuntimeError:
        encoder = "h264_nvenc" if has_nvenc_support() else "libx264"
        _run_ffmpeg(
            [
                settings.ffmpeg_bin,
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat_manifest),
                "-c:v",
                encoder,
                "-preset",
                "p4" if encoder == "h264_nvenc" else "medium",
                "-c:a",
                "aac",
                str(merged_file),
            ]
        )

    if merged_file.suffix.lower() == requested_output_path.suffix.lower():
        merged_file.replace(requested_output_path)
        return requested_output_path

    try:
        _run_ffmpeg(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                str(merged_file),
                "-c",
                "copy",
                str(requested_output_path),
            ]
        )
    except RuntimeError:
        encoder = "h264_nvenc" if has_nvenc_support() else "libx264"
        _run_ffmpeg(
            [
                settings.ffmpeg_bin,
                "-y",
                "-i",
                str(merged_file),
                "-c:v",
                encoder,
                "-preset",
                "p4" if encoder == "h264_nvenc" else "medium",
                "-c:a",
                "aac",
                str(requested_output_path),
            ]
        )

    return requested_output_path
