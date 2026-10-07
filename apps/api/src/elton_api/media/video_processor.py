"""Fail-closed MP4 validation and trusted derivative generation.

The API never publishes an uploaded video as-is. ``ffprobe`` first verifies
that the input is an MP4 with one H.264 or HEVC video stream, optional AAC
audio, and bounded dimensions/duration. ``ffmpeg`` then writes a
server-selected H.264 MP4 derivative with user metadata and chapters removed.
The derivative is probed again before it can be promoted from quarantine.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
from typing import Any


MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_VIDEO_DURATION_SECONDS = 60.0
MAX_VIDEO_DIMENSION = 8192
MAX_VIDEO_PIXELS = 40_000_000
MAX_VIDEO_OUTPUT_BYTES = 50 * 1024 * 1024
VIDEO_PROCESS_TIMEOUT_SECONDS = 30.0
SUPPORTED_CONTAINER = "mov,mp4,m4a,3gp,3g2,mj2"
VIDEO_RUNTIME_HELP = "Video processing is unavailable. Configure ELTON_FFMPEG_BINARY and ELTON_FFPROBE_BINARY with executable paths to FFmpeg/ffprobe, then restart the API."


class VideoValidationError(ValueError):
    """The upload is not safe or the trusted decoder is unavailable."""


@dataclass(frozen=True)
class ValidatedVideo:
    content_type: str
    extension: str
    width: int
    height: int
    byte_size: int
    duration_seconds: float
    video_codec: str
    audio_codec: str | None
    decoder_verified: bool = True


def _bad(message: str) -> VideoValidationError:
    return VideoValidationError(message)


def verify_video_runtime(*, ffmpeg_binary: str, ffprobe_binary: str, timeout_seconds: float) -> None:
    """Check the configured tools and required codecs without uploaded media.

    This is an internal startup check, not a public commercial capability.
    Explicit executable settings take precedence; no search of user storage.
    """
    for binary, option, required in (
        (ffprobe_binary, "-version", set()),
        (ffmpeg_binary, "-encoders", {"libx264", "aac"}),
        (ffmpeg_binary, "-decoders", {"h264", "hevc", "aac"}),
    ):
        try:
            result = subprocess.run(
                [binary, "-hide_banner", option], shell=False, check=False,
                capture_output=True, text=True, timeout=min(timeout_seconds, 5.0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise _bad(VIDEO_RUNTIME_HELP) from exc
        codecs = {columns[1] for line in result.stdout.splitlines() if len(columns := line.split()) >= 2}
        if result.returncode != 0 or not required.issubset(codecs) or (option == "-version" and not result.stdout.startswith("ffprobe version ")):
            raise _bad(VIDEO_RUNTIME_HELP)


def _check_dimensions(width: Any, height: Any) -> tuple[int, int]:
    if not isinstance(width, int) or not isinstance(height, int):
        raise _bad("video dimensions are missing")
    if width <= 0 or height <= 0 or width > MAX_VIDEO_DIMENSION or height > MAX_VIDEO_DIMENSION:
        raise _bad("video dimensions exceed the limit")
    if width * height > MAX_VIDEO_PIXELS:
        raise _bad("video pixel count exceeds the safety limit")
    return width, height


def _probe(path: Path, *, ffprobe_binary: str, timeout_seconds: float) -> dict[str, Any]:
    try:
        completed = subprocess.run(
            [ffprobe_binary, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            shell=False,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except FileNotFoundError as exc:
        raise _bad("video decoder unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise _bad("video decoder timed out") from exc
    except OSError as exc:
        raise _bad("video decoder unavailable") from exc
    if completed.returncode != 0:
        raise _bad("video decoder rejected container")
    try:
        payload = json.loads(completed.stdout)
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        raise _bad("video decoder returned invalid metadata") from exc
    if not isinstance(payload, dict):
        raise _bad("video decoder returned invalid metadata")
    return payload


def _validated_probe(payload: dict[str, Any]) -> tuple[int, int, float, str, str | None]:
    fmt = payload.get("format")
    streams = payload.get("streams")
    if not isinstance(fmt, dict) or not isinstance(streams, list):
        raise _bad("video metadata is incomplete")
    if fmt.get("format_name") != SUPPORTED_CONTAINER:
        raise _bad("video container is not MP4")
    try:
        duration = float(fmt["duration"])
    except (KeyError, TypeError, ValueError) as exc:
        raise _bad("video duration is missing") from exc
    if not 0 < duration <= MAX_VIDEO_DURATION_SECONDS:
        raise _bad("video duration exceeds the limit")

    video_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") == "audio"]
    other_streams = [stream for stream in streams if isinstance(stream, dict) and stream.get("codec_type") not in {"video", "audio"}]
    if len(video_streams) != 1 or len(audio_streams) > 1 or other_streams:
        raise _bad("video stream layout is unsupported")
    video = video_streams[0]
    video_codec = video.get("codec_name")
    if video_codec not in {"h264", "hevc"}:
        raise _bad("video codec is unsupported")
    width, height = _check_dimensions(video.get("width"), video.get("height"))
    audio_codec = audio_streams[0].get("codec_name") if audio_streams else None
    if audio_codec is not None and audio_codec != "aac":
        raise _bad("audio codec is unsupported")
    return width, height, duration, video_codec, audio_codec


def validate_video(path: Path, *, declared_content_type: str, filename: str, ffprobe_binary: str = "ffprobe", timeout_seconds: float = VIDEO_PROCESS_TIMEOUT_SECONDS) -> ValidatedVideo:
    """Validate the source MP4 using the trusted ffprobe binary."""
    path = Path(path)
    if not path.is_file() or path.is_symlink():
        raise _bad("video source is unavailable")
    if path.stat().st_size <= 0 or path.stat().st_size > MAX_VIDEO_BYTES:
        raise _bad("video exceeds the byte limit")
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise _bad("filename traversal is not allowed")
    if Path(filename).suffix.lower() != ".mp4" or declared_content_type.lower().strip() != "video/mp4":
        raise _bad("MP4 MIME type and extension are required")
    width, height, duration, video_codec, audio_codec = _validated_probe(_probe(path, ffprobe_binary=ffprobe_binary, timeout_seconds=timeout_seconds))
    return ValidatedVideo("video/mp4", ".mp4", width, height, path.stat().st_size, duration, video_codec, audio_codec)


def transcode_and_reencode(path: Path, destination: Path, *, declared_content_type: str, filename: str, ffmpeg_binary: str = "ffmpeg", ffprobe_binary: str = "ffprobe", timeout_seconds: float = VIDEO_PROCESS_TIMEOUT_SECONDS) -> ValidatedVideo:
    """Create and verify a metadata-free H.264/AAC MP4 derivative."""
    validate_video(path, declared_content_type=declared_content_type, filename=filename, ffprobe_binary=ffprobe_binary, timeout_seconds=timeout_seconds)
    destination = Path(destination)
    destination.unlink(missing_ok=True)
    args = [ffmpeg_binary, "-v", "error", "-nostdin", "-i", str(path), "-map", "0:v:0", "-map", "0:a:0?", "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k", "-map_metadata", "-1", "-map_chapters", "-1", "-movflags", "+faststart", "-threads", "1", "-y", str(destination)]
    try:
        completed = subprocess.run(args, shell=False, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except FileNotFoundError as exc:
        raise _bad("video encoder unavailable") from exc
    except subprocess.TimeoutExpired as exc:
        raise _bad("video encoder timed out") from exc
    except OSError as exc:
        raise _bad("video encoder unavailable") from exc
    if completed.returncode != 0 or not destination.is_file():
        destination.unlink(missing_ok=True)
        raise _bad("video encoder rejected input")
    if destination.stat().st_size <= 0 or destination.stat().st_size > MAX_VIDEO_OUTPUT_BYTES:
        destination.unlink(missing_ok=True)
        raise _bad("video derivative exceeds the byte limit")
    try:
        width, height, duration, video_codec, audio_codec = _validated_probe(_probe(destination, ffprobe_binary=ffprobe_binary, timeout_seconds=timeout_seconds))
    except Exception:
        destination.unlink(missing_ok=True)
        raise
    return ValidatedVideo("video/mp4", ".mp4", width, height, destination.stat().st_size, duration, video_codec, audio_codec)


def reject_video() -> None:
    """Compatibility helper for old callers; uploads use the verified pipeline."""
    raise _bad("video validation must run through transcode_and_reencode")
