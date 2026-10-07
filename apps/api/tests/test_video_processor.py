"""Trusted MP4 validation/transcode policy tests."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess

import pytest

from elton_api.media.video_processor import (
    MAX_VIDEO_DURATION_SECONDS,
    VideoValidationError,
    transcode_and_reencode,
    validate_video,
)


FIXTURE = Path(__file__).parent / "fixtures" / "synthetic.mp4"


def _probe(*, codec: str = "h264", audio: str | None = "aac", duration: str = "1.0") -> dict:
    streams = [{"index": 0, "codec_type": "video", "codec_name": codec, "width": 320, "height": 240}]
    if audio:
        streams.append({"index": 1, "codec_type": "audio", "codec_name": audio})
    return {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": duration}, "streams": streams}


def _completed(payload: dict) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(payload), stderr="")


def test_valid_synthetic_mp4_is_probed_with_strict_limits(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args, **kwargs):
        calls.append(list(args))
        return _completed(_probe())

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", fake_run)
    result = validate_video(FIXTURE, declared_content_type="video/mp4", filename="demo.mp4")

    assert result.content_type == "video/mp4"
    assert result.decoder_verified is True
    assert result.duration_seconds == 1.0
    assert calls[0][0] == "ffprobe"
    assert "-show_format" in calls[0] and "-show_streams" in calls[0]
    assert calls[0][-1] == str(FIXTURE)


def test_mp4_without_audio_is_allowed(monkeypatch):
    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", lambda *args, **kwargs: _completed(_probe(audio=None)))
    result = validate_video(FIXTURE, declared_content_type="video/mp4", filename="demo.mp4")
    assert result.audio_codec is None


def test_hevc_input_is_allowed_for_server_transcode(monkeypatch):
    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", lambda *args, **kwargs: _completed(_probe(codec="hevc")))

    result = validate_video(FIXTURE, declared_content_type="video/mp4", filename="phone-video.mp4")

    assert result.video_codec == "hevc"


@pytest.mark.parametrize(
    "filename,content_type",
    [("demo.mov", "video/mp4"), ("demo.mp4", "video/quicktime"), ("demo.mp4", "image/png")],
)
def test_mp4_requires_matching_filename_and_mime(tmp_path, filename, content_type):
    source = tmp_path / "demo.mp4"
    source.write_bytes(FIXTURE.read_bytes())
    with pytest.raises(VideoValidationError):
        validate_video(source, declared_content_type=content_type, filename=filename)


@pytest.mark.parametrize(
    "probe",
    [
        _probe(codec="mpeg4"),
        _probe(duration=str(MAX_VIDEO_DURATION_SECONDS + 0.01)),
        {"format": {"format_name": "avi", "duration": "1"}, "streams": []},
        {"format": {"format_name": "mov,mp4,m4a,3gp,3g2,mj2", "duration": "1"}, "streams": [{"codec_type": "subtitle", "codec_name": "mov_text"}]},
    ],
)
def test_unsafe_container_codec_or_duration_fails_closed(monkeypatch, tmp_path, probe):
    source = tmp_path / "demo.mp4"
    source.write_bytes(FIXTURE.read_bytes())
    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", lambda *args, **kwargs: _completed(probe))
    with pytest.raises(VideoValidationError):
        validate_video(source, declared_content_type="video/mp4", filename="demo.mp4")


def test_transcode_removes_metadata_and_rechecks_output(monkeypatch, tmp_path):
    source = tmp_path / "demo.mp4"
    source.write_bytes(FIXTURE.read_bytes())
    destination = tmp_path / "demo.decoded"
    calls: list[list[str]] = []
    probe_count = 0

    def fake_run(args, **kwargs):
        nonlocal probe_count
        args = list(args)
        calls.append(args)
        if args[0] == "ffprobe":
            probe_count += 1
            return _completed(_probe())
        Path(args[-1]).write_bytes(b"synthetic-clean-mp4")
        return subprocess.CompletedProcess(args=args, returncode=0, stdout="", stderr="")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", fake_run)
    result = transcode_and_reencode(
        source,
        destination,
        declared_content_type="video/mp4",
        filename="demo.mp4",
    )

    assert result.content_type == "video/mp4"
    assert result.decoder_verified is True
    assert destination.exists()
    assert probe_count == 2
    ffmpeg = calls[1]
    assert "-map_metadata" in ffmpeg and "-1" in ffmpeg
    assert "-map_chapters" in ffmpeg and "-1" in ffmpeg
    assert "-c:v" in ffmpeg and "libx264" in ffmpeg
    assert "-movflags" in ffmpeg and "+faststart" in ffmpeg


def test_missing_ffprobe_is_a_capability_error(monkeypatch, tmp_path):
    source = tmp_path / "demo.mp4"
    source.write_bytes(FIXTURE.read_bytes())

    def missing(*args, **kwargs):
        raise FileNotFoundError("ffprobe")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", missing)
    with pytest.raises(VideoValidationError, match="decoder unavailable"):
        validate_video(source, declared_content_type="video/mp4", filename="demo.mp4")
