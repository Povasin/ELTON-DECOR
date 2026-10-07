"""Opt-in real FFmpeg upload checks using only generated synthetic media."""
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from elton_api.admin.auth import AdminPrincipal
from elton_api.config import Settings
from elton_api.guest.service import database_session
from elton_api.main import create_app
from test_admin_media import _Session


@pytest.fixture
def video_tools():
    ffmpeg = os.environ.get("ELTON_TEST_FFMPEG_BINARY") or shutil.which("ffmpeg")
    ffprobe = os.environ.get("ELTON_TEST_FFPROBE_BINARY") or shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        pytest.skip("Set ELTON_TEST_FFMPEG_BINARY and ELTON_TEST_FFPROBE_BINARY to a verified FFmpeg runtime")
    return ffmpeg, ffprobe


def synthetic_video(directory: Path, ffmpeg: str, *, codec: str, duration: int = 1) -> Path:
    source = directory / f"synthetic-{codec}-{duration}.mp4"
    subprocess.run(
        [ffmpeg, "-v", "error", "-nostdin", "-f", "lavfi", "-i",
         f"color=c=blue:s=32x32:r=1:d={duration}", "-an", "-c:v", codec,
         "-threads", "1", "-metadata", "comment=synthetic runtime check", "-y", str(source)],
        check=True, capture_output=True, timeout=30,
    )
    return source


@pytest.mark.parametrize("codec", ["libx264", "libx265"])
def test_real_mp4_upload_publishes_playable_h264_derivative(video_tools, tmp_path, settings_values, unreachable_database_url, monkeypatch, codec):
    ffmpeg, ffprobe = video_tools
    source = synthetic_video(tmp_path, ffmpeg, codec=codec)
    product = SimpleNamespace(id=uuid4(), version=1)
    session = _Session(product)
    admin = AdminPrincipal(uuid4(), uuid4(), frozenset({"catalog.write"}))
    monkeypatch.setattr("elton_api.admin.auth.require_admin_mutation", lambda *_args: admin)
    app = create_app(Settings(database_url=unreachable_database_url, media_storage_root=tmp_path / "media", ffmpeg_binary=ffmpeg, ffprobe_binary=ffprobe, **settings_values))
    app.dependency_overrides[database_session] = lambda: session
    assert app.state.video_runtime_available is True
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/products/{product.id}/media", headers={"If-Match": '"1"'}, files={"file": ("synthetic.mp4", source.read_bytes(), "video/mp4")})
        assert response.status_code == 201
        assert response.json()["type"] == "video"
        assert response.headers["etag"] == '"2"'
        session.product = session.added[0]
        public = client.get(response.json()["url"])
        assert public.status_code == 200
        assert public.headers["content-type"] == "video/mp4"
        assert public.headers["x-content-type-options"] == "nosniff"
    derivative = next((tmp_path / "media" / "clean").iterdir())
    decoded = subprocess.run([ffprobe, "-v", "error", "-show_format", "-show_streams", "-of", "json", str(derivative)], capture_output=True, text=True, check=True, timeout=10)
    payload = json.loads(decoded.stdout)
    assert payload["streams"][0]["codec_name"] == "h264"
    assert "comment" not in payload["format"].get("tags", {})
    assert not list((tmp_path / "media" / "quarantine").iterdir())


@pytest.mark.parametrize("codec,duration", [("mpeg4", 1), ("libx264", 61)])
def test_real_invalid_mp4_upload_creates_no_public_pointer(video_tools, tmp_path, settings_values, unreachable_database_url, monkeypatch, codec, duration):
    ffmpeg, ffprobe = video_tools
    source = synthetic_video(tmp_path, ffmpeg, codec=codec, duration=duration)
    product = SimpleNamespace(id=uuid4(), version=1)
    session = _Session(product)
    admin = AdminPrincipal(uuid4(), uuid4(), frozenset({"catalog.write"}))
    monkeypatch.setattr("elton_api.admin.auth.require_admin_mutation", lambda *_args: admin)
    app = create_app(Settings(database_url=unreachable_database_url, media_storage_root=tmp_path / "media", ffmpeg_binary=ffmpeg, ffprobe_binary=ffprobe, **settings_values))
    app.dependency_overrides[database_session] = lambda: session
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/products/{product.id}/media", headers={"If-Match": '"1"'}, files={"file": ("synthetic.mp4", source.read_bytes(), "video/mp4")})
    assert response.status_code == 422
    assert response.json()["code"] == "MEDIA_INVALID"
    assert product.version == 1
    assert session.added == []
    assert not list((tmp_path / "media" / "clean").iterdir())
    assert not list((tmp_path / "media" / "quarantine").iterdir())


def test_missing_runtime_returns_actionable_upload_error(tmp_path, settings_values, unreachable_database_url, monkeypatch):
    product = SimpleNamespace(id=uuid4(), version=1)
    session = _Session(product)
    admin = AdminPrincipal(uuid4(), uuid4(), frozenset({"catalog.write"}))
    monkeypatch.setattr("elton_api.admin.auth.require_admin_mutation", lambda *_args: admin)
    app = create_app(Settings(database_url=unreachable_database_url, media_storage_root=tmp_path / "media", ffprobe_binary=str(tmp_path / "missing-ffprobe"), **settings_values))
    app.dependency_overrides[database_session] = lambda: session
    with TestClient(app) as client:
        response = client.post(f"/api/v1/admin/products/{product.id}/media", headers={"If-Match": '"1"'}, files={"file": ("synthetic.mp4", io.BytesIO(b"synthetic"), "video/mp4")})
    assert response.status_code == 409
    assert response.json()["code"] == "CAPABILITY_DISABLED"
    assert "ELTON_FFMPEG_BINARY" in response.json()["detail"]
    assert "ELTON_FFPROBE_BINARY" in response.json()["detail"]
    assert "restart the API" in response.json()["detail"]
    assert str(tmp_path) not in response.json()["detail"]
    assert session.added == []
    assert not list((tmp_path / "media" / "clean").iterdir())
    assert not list((tmp_path / "media" / "quarantine").iterdir())
