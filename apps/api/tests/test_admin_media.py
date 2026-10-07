"""Task 6 media validation and protected storage tests."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4
import struct
import zlib
from PIL import Image

import pytest
from fastapi import HTTPException, Response
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from elton_api.config import Settings
from elton_api.main import create_app
from elton_api.media.image_processor import MediaValidationError, decode_and_reencode, validate_image
from elton_api.media.local_storage import LocalMediaStorage
from elton_api.media.service import MediaService, _defer_commit_cleanup, _defer_rollback_cleanup
from elton_api.admin.auth import AdminPrincipal, admin_if_match
from elton_api.guest.service import database_session
from elton_api.catalog.service import public_media
from elton_api.media import routes as media_routes


def _png(width: int = 1, height: int = 1) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    scanline = (b"\x00" + bytes([180, 120, 80]) * width) * height
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(scanline)) + chunk(b"IEND", b"")


class _Session:
    def __init__(self, product):
        self.product = product
        self.added = []
        self.executed = []

    def scalar(self, _statement):
        return self.product

    def add(self, value):
        self.added.append(value)

    def execute(self, statement, *args, **kwargs):
        self.executed.append((statement, args, kwargs))
        return None

    def flush(self):
        return None


def _admin() -> AdminPrincipal:
    return AdminPrincipal(id=uuid4(), session_id=uuid4(), permissions=frozenset({"catalog.write"}))


def test_png_signature_mime_and_dimensions_are_validated(tmp_path):
    image = tmp_path / "flower.png"
    image.write_bytes(_png(2, 3))
    result = validate_image(image, declared_content_type="image/png", filename="flower.png")
    assert (result.width, result.height, result.content_type) == (2, 3, "image/png")


@pytest.mark.parametrize(
    "filename,content_type,data",
    [
        ("flower.jpg", "image/jpeg", _png()),
        ("flower.png", "image/jpeg", _png()),
        ("../flower.png", "image/png", _png()),
        ("flower.svg", "image/svg+xml", b"<svg><script>alert(1)</script></svg>"),
    ],
)
def test_spoofed_mime_extension_markup_and_traversal_are_rejected(tmp_path, filename, content_type, data):
    image = tmp_path / "upload"
    image.write_bytes(data)
    with pytest.raises(MediaValidationError):
        validate_image(image, declared_content_type=content_type, filename=filename)


def test_over_dimensioned_png_is_rejected_before_decode(tmp_path):
    image = tmp_path / "huge.png"
    image.write_bytes(_png(8193, 1))
    with pytest.raises(MediaValidationError):
        validate_image(image, declared_content_type="image/png", filename="huge.png")


def test_oversized_stream_is_rejected_and_quarantine_is_cleaned(tmp_path):
    storage = LocalMediaStorage(tmp_path / "media")
    source = type("Source", (), {"read": lambda self, _size: b"x" * (10 * 1024 * 1024 + 1)})()
    with pytest.raises(MediaValidationError):
        storage.quarantine_stream(source)
    assert not list((tmp_path / "media" / "quarantine").iterdir())


def test_trusted_decoder_reencodes_to_clean_metadata_free_webp(tmp_path):
    storage = LocalMediaStorage(tmp_path / "media")
    item = storage.quarantine_stream(__import__("io").BytesIO(_png()))
    image = tmp_path / "image.png"
    image.write_bytes(_png())
    validated = validate_image(image, declared_content_type="image/png", filename="image.png")
    derivative = item.path.with_suffix(".decoded")
    decoded = decode_and_reencode(item.path, derivative)
    key, published = storage.publish(item, decoded, derivative)
    assert key.endswith(".webp") and published.read_bytes()[:4] == b"RIFF"
    assert not item.path.exists()
    with pytest.raises(ValueError):
        storage._uuid_name(item.token, "../secret")


def test_decoder_strips_exif_and_rejects_corrupt_raster(tmp_path):
    source = tmp_path / "source.jpg"
    image = Image.new("RGB", (2, 3), (100, 50, 25))
    exif = Image.Exif()
    exif[0x010E] = "private camera note"
    image.save(source, format="JPEG", exif=exif)
    output = tmp_path / "output.webp"
    decoded = decode_and_reencode(source, output)
    assert decoded.content_type == "image/webp"
    with Image.open(output) as derivative:
        assert derivative.getexif() == {}
        assert derivative.size == (2, 3)
    corrupt = tmp_path / "corrupt.png"
    corrupt.write_bytes(b"\x89PNG\r\n\x1a\nnot a raster")
    with pytest.raises(MediaValidationError):
        decode_and_reencode(corrupt, tmp_path / "bad.webp")


def test_clean_derivative_uses_actual_public_api_url_and_route(tmp_path, settings_values, unreachable_database_url):
    token = uuid4()
    storage = LocalMediaStorage(tmp_path / "media")
    derivative = storage.clean / f"{token}.webp"
    Image.new("RGB", (1, 1), (10, 20, 30)).save(derivative, format="WEBP")
    row = SimpleNamespace(
        id=uuid4(), storage_key=f"clean/{token}.webp", media_type="image",
        alt_text="Synthetic", position=0, scan_state="clean", metadata_json={"content_type": "image/webp"},
    )
    assert public_media([row])[0].url == f"/api/v1/media/clean/{token}.webp"
    app = create_app(Settings(database_url=unreachable_database_url, media_storage_root=tmp_path / "media", **settings_values))
    app.dependency_overrides[database_session] = lambda: SimpleNamespace(scalar=lambda _statement: row)
    with TestClient(app) as client:
        response = client.get(f"/api/v1/media/clean/{token}.webp")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/webp"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_stale_if_match_cleans_quarantine_and_does_not_publish(tmp_path):
    product = SimpleNamespace(id=uuid4(), version=2)
    session = _Session(product)
    storage = LocalMediaStorage(tmp_path / "media")
    with pytest.raises(HTTPException) as error:
        MediaService(session, storage).create_image(
            admin=_admin(), product_id=product.id, expected_version=1,
            source=__import__("io").BytesIO(_png()), filename="image.png",
            declared_content_type="image/png", alt_text="demo", position=0,
            trace_id="trace",
        )
    assert error.value.status_code == 409
    assert not list(storage.quarantine.iterdir())
    assert not list(storage.clean.iterdir())


def test_trusted_decoder_creates_only_clean_derivative_row(tmp_path):
    product = SimpleNamespace(id=uuid4(), version=7)
    session = _Session(product)
    storage = LocalMediaStorage(tmp_path / "media")
    result = MediaService(session, storage).create_image(
        admin=_admin(), product_id=product.id, expected_version=7,
        source=__import__("io").BytesIO(_png()), filename="image.png",
        declared_content_type="image/png", alt_text="Synthetic", position=2,
        trace_id="trace",
    )
    assert result.url.endswith(".webp")
    assert product.version == 8
    assert len(session.added) == 1
    assert session.added[0].metadata_json["content_type"] == "image/webp"
    assert len(list(storage.clean.iterdir())) == 1
    assert not list(storage.quarantine.iterdir())


def test_trusted_video_pipeline_publishes_clean_mp4(monkeypatch, tmp_path):
    product = SimpleNamespace(id=uuid4(), version=3)
    session = _Session(product)
    storage = LocalMediaStorage(tmp_path / "media")

    def fake_transcode(source, destination, **kwargs):
        destination.write_bytes(b"synthetic-clean-mp4")
        from elton_api.media.video_processor import ValidatedVideo
        return ValidatedVideo("video/mp4", ".mp4", 320, 240, destination.stat().st_size, 1.0, "h264", "aac")

    monkeypatch.setattr("elton_api.media.service.transcode_and_reencode", fake_transcode)
    result = MediaService(session, storage).create_video(
        admin=_admin(), product_id=product.id, expected_version=3,
        source=__import__("io").BytesIO(b"synthetic-mp4"), filename="demo.mp4",
        declared_content_type="video/mp4", alt_text="Demo", position=0, trace_id="trace",
    )
    assert result.type == "video"
    assert result.url.endswith(".mp4")
    assert product.version == 4
    assert len(session.added) == 1
    assert session.added[0].media_type == "video"
    assert session.added[0].metadata_json["video_codec"] == "h264"
    assert len(list(storage.clean.iterdir())) == 1


def test_oversized_service_stream_maps_to_media_problem_and_cleans(tmp_path):
    product = SimpleNamespace(id=uuid4(), version=1)
    storage = LocalMediaStorage(tmp_path / "media")
    source = type("Source", (), {"read": lambda self, _size: b"x" * (10 * 1024 * 1024 + 1)})()
    with pytest.raises(HTTPException) as error:
        MediaService(_Session(product), storage).create_image(
            admin=_admin(), product_id=product.id, expected_version=1,
            source=source, filename="image.png", declared_content_type="image/png",
            alt_text="", position=0, trace_id=None,
        )
    assert error.value.status_code == 422 and error.value.detail == "MEDIA_INVALID"
    assert not list(storage.quarantine.iterdir()) and not list(storage.clean.iterdir())


def test_cleanup_orphans_keeps_live_clean_product_media(tmp_path):
    storage = LocalMediaStorage(tmp_path / "media")
    live = uuid4()
    stale = uuid4()
    quarantine = uuid4()
    (storage.clean / f"{live}.png").write_bytes(b"live")
    (storage.clean / f"{stale}.png").write_bytes(b"stale")
    (storage.quarantine / str(quarantine)).write_bytes(b"quarantine")
    import os, time
    old = time.time() - 7200
    for path in (storage.clean / f"{live}.png", storage.clean / f"{stale}.png", storage.quarantine / str(quarantine)):
        os.utime(path, (old, old))
    db = type("DB", (), {"scalars": lambda self, _statement: iter([f"clean/{live}.png"])})()
    assert storage.cleanup_orphans(db) == 2
    assert (storage.clean / f"{live}.png").exists()
    assert not (storage.clean / f"{stale}.png").exists()
    assert not (storage.quarantine / str(quarantine)).exists()


def test_filesystem_cleanup_follows_db_commit_or_rollback(tmp_path):
    storage = LocalMediaStorage(tmp_path / "media")
    committed = storage.clean / f"{uuid4()}.png"
    committed.write_bytes(b"committed")
    session = Session()
    _defer_commit_cleanup(session, storage, committed)
    session.begin()
    session.commit()
    assert not committed.exists()

    rolled_back = storage.clean / f"{uuid4()}.png"
    rolled_back.write_bytes(b"rolled-back")
    session = Session()
    _defer_rollback_cleanup(session, storage, rolled_back)
    session.begin()
    session.rollback()
    assert not rolled_back.exists()




def test_video_route_is_fail_closed_without_trusted_decoder(settings_values, unreachable_database_url, monkeypatch, tmp_path):
    app = create_app(Settings(database_url=unreachable_database_url, **settings_values))
    paths = app.openapi()["paths"]
    assert "/api/v1/admin/products/{product_id}/media" in paths
    assert "/api/v1/media/{storage_key}" not in paths  # deliberately omitted from OpenAPI
    source = tmp_path / "demo.mp4"
    source.write_bytes(b"synthetic")
    def missing(*args, **kwargs):
        raise FileNotFoundError("ffprobe")
    monkeypatch.setattr("elton_api.media.video_processor.subprocess.run", missing)
    from elton_api.media.video_processor import VideoValidationError, validate_video
    with pytest.raises(VideoValidationError, match="decoder unavailable"):
        validate_video(source, declared_content_type="video/mp4", filename="demo.mp4")


def test_admin_if_match_still_fails_closed_for_media_commands():
    with pytest.raises(HTTPException) as error:
        admin_if_match(None)
    assert error.value.status_code == 428
    assert admin_if_match('"12"') == 12


def test_delete_media_route_sends_a_real_no_content_response(monkeypatch, tmp_path):
    calls = []

    class FakeMediaService:
        def __init__(self, _session, _storage):
            pass

        def delete_media(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(media_routes, "MediaService", FakeMediaService)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(media_storage_root=tmp_path))),
        state=SimpleNamespace(trace_id="trace"),
    )
    response = media_routes.delete_media(
        uuid4(), uuid4(), request, Response(), _admin(), 4, object(),
    )

    assert response.status_code == 204
    assert response.headers["etag"] == '"5"'
    assert calls and calls[0]["expected_version"] == 4
