"""Runtime discovery must reject an incomplete toolchain before an upload."""
import subprocess

from elton_api.config import Settings
from elton_api.main import create_app


def test_app_verifies_configured_video_toolchain(settings_values, unreachable_database_url, monkeypatch):
    def available(args, **kwargs):
        if "-encoders" in args:
            output = " V..... libx264 H.264\n A..... aac AAC"
        elif "-decoders" in args:
            output = " V..... h264 H.264\n V..... hevc HEVC\n A..... aac AAC"
        else:
            output = "ffprobe version synthetic"
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", available)
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    assert getattr(app.state, "video_runtime_available", False) is True


def test_app_reports_missing_video_runtime_without_exposing_process_output(settings_values, unreachable_database_url, monkeypatch, caplog):
    def missing(*args, **kwargs):
        raise FileNotFoundError("private runtime path")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", missing)
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    assert getattr(app.state, "video_runtime_available", True) is False
    assert "ELTON_FFMPEG_BINARY" in caplog.text
    assert "ELTON_FFPROBE_BINARY" in caplog.text
    assert "private runtime path" not in caplog.text


def test_app_disables_video_when_hevc_decoder_is_missing(settings_values, unreachable_database_url, monkeypatch):
    def incomplete(args, **kwargs):
        if "-version" in args:
            output = "ffprobe version synthetic"
        else:
            output = " V..... libx264 H.264\n A..... aac AAC" if "-encoders" in args else " V..... h264 H.264\n A..... aac AAC"
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", incomplete)
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    assert getattr(app.state, "video_runtime_available", True) is False


def test_app_rejects_a_non_ffprobe_executable(settings_values, unreachable_database_url, monkeypatch):
    def wrong_probe(args, **kwargs):
        output = "ffmpeg version synthetic" if "-version" in args else " V..... libx264 H.264\n A..... aac AAC\n V..... h264 H.264\n V..... hevc HEVC"
        return subprocess.CompletedProcess(args, 0, stdout=output, stderr="")

    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", wrong_probe)
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    assert app.state.video_runtime_available is False
