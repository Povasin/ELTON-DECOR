"""Protected admin media routes.

The route uses a small streaming multipart reader so the API does not need to
materialize an upload in request memory. It accepts exactly one file field
named ``file`` plus ``alt_text`` and ``position``.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
import tempfile
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy.orm import Session

from elton_api.admin.auth import AdminPrincipal, admin_dependency, admin_if_match
from elton_api.guest.service import database_session
from elton_api.media.local_storage import LocalMediaStorage
from elton_api.media.schemas import MediaDTO, MediaUploadMetadata
from elton_api.media.service import MediaService
from elton_api.media.video_processor import MAX_VIDEO_BYTES
from elton_database.models.catalog import ProductMedia
from sqlalchemy import select


router = APIRouter(prefix="/api/v1/admin", tags=["admin media"])
public_router = APIRouter(prefix="/api/v1", tags=["public media"])


@dataclass
class _Part:
    name: str
    filename: str | None
    content_type: str
    path: Path | None = None
    value: bytes = b""


def _boundary(content_type: str) -> bytes:
    match = re.search(r"boundary=(?:\"([^\"]+)\"|([^;\s]+))", content_type, re.I)
    if not match:
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    try:
        value = (match.group(1) or match.group(2)).encode("ascii", "strict")
    except UnicodeEncodeError as exc:
        raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc
    if not 1 <= len(value) <= 70 or any(byte < 0x20 or byte > 0x7E for byte in value):
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    return b"--" + value


def _headers(raw: bytes) -> tuple[str, str | None, str]:
    values: dict[str, str] = {}
    for line in raw.split(b"\r\n"):
        if not line or b":" not in line:
            continue
        key, value = line.split(b":", 1)
        values[key.decode("ascii", "strict").lower()] = value.decode("utf-8", "strict").strip()
    disposition = values.get("content-disposition", "")
    name_match = re.search(r"(?:^|;)\s*name=\"([^\"]+)\"", disposition)
    if not name_match:
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    file_match = re.search(r"(?:^|;)\s*filename=\"([^\"]*)\"", disposition)
    filename = file_match.group(1) if file_match else None
    if filename is not None and ("\x00" in filename or "\r" in filename or "\n" in filename):
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    return name_match.group(1), filename, values.get("content-type", "application/octet-stream")


async def _parse_multipart(request: Request) -> tuple[_Part, dict[str, bytes]]:
    """Parse one upload and remove every temporary part on all failures."""
    temp_paths: set[Path] = set()
    temp_handles: set = set()
    try:
        return await _parse_multipart_unchecked(request, temp_paths, temp_handles)
    except BaseException:
        for handle in list(temp_handles):
            handle.close()
        for path in temp_paths:
            path.unlink(missing_ok=True)
        raise


async def _parse_multipart_unchecked(request: Request, temp_paths: set[Path], temp_handles: set) -> tuple[_Part, dict[str, bytes]]:
    boundary = _boundary(request.headers.get("content-type", ""))
    marker = b"\r\n" + boundary
    buffer = bytearray()
    total = 0
    parts: list[_Part] = []
    current: _Part | None = None
    current_file = None
    current_field = bytearray()
    state = "preamble"
    # Accept the largest supported media type at the multipart boundary. The
    # image/video services enforce their own quarantine limits while copying.
    file_limit = MAX_VIDEO_BYTES + 256 * 1024

    def drain_body(final: bool = False) -> bool:
        nonlocal current_file, current_field, current
        index = buffer.find(marker)
        if index < 0 and not final:
            keep = len(marker) + 4
            if len(buffer) > keep:
                payload = bytes(buffer[:-keep])
                del buffer[:-keep]
                if current_file is not None:
                    current_file.write(payload)
                else:
                    current_field.extend(payload)
            return False
        if index < 0:
            raise HTTPException(status_code=422, detail="MEDIA_INVALID")
        payload = bytes(buffer[:index])
        del buffer[:index + len(marker)]
        if current_file is not None:
            current_file.write(payload)
            temp_handles.discard(current_file)
            current_file.close()
            current_file = None
        else:
            current_field.extend(payload)
        if current is None:
            raise HTTPException(status_code=422, detail="MEDIA_INVALID")
        if current.filename is None:
            current.value = bytes(current_field)
        parts.append(current)
        current_field = bytearray()
        current = None
        return True

    async for chunk in request.stream():
        total += len(chunk)
        if total > file_limit + 64 * 1024:
            raise HTTPException(status_code=422, detail="MEDIA_INVALID")
        buffer.extend(chunk)
        while True:
            if state == "preamble":
                if not buffer.startswith(boundary):
                    index = buffer.find(boundary)
                    if index < 0:
                        if len(buffer) > len(boundary):
                            del buffer[:-len(boundary)]
                        break
                    del buffer[:index]
                if len(buffer) < len(boundary) + 2:
                    break
                del buffer[:len(boundary)]
                if buffer[:2] == b"--":
                    state = "done"
                    del buffer[:2]
                    break
                if buffer[:2] != b"\r\n":
                    raise HTTPException(status_code=422, detail="MEDIA_INVALID")
                del buffer[:2]
                state = "headers"
            elif state == "headers":
                index = buffer.find(b"\r\n\r\n")
                if index < 0:
                    if len(buffer) > 16 * 1024:
                        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
                    break
                try:
                    name, filename, content_type = _headers(bytes(buffer[:index]))
                except (UnicodeError, ValueError) as exc:
                    raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc
                del buffer[:index + 4]
                current = _Part(name, filename, content_type)
                if filename is not None:
                    temporary = tempfile.NamedTemporaryFile(prefix="elton-media-", suffix=".upload", delete=False)
                    current.path = Path(temporary.name)
                    temp_paths.add(current.path)
                    temporary.close()
                    current_file = current.path.open("wb")
                    temp_handles.add(current_file)
                state = "body"
            elif state == "body":
                if not drain_body():
                    break
                if len(buffer) < 2:
                    break
                if buffer.startswith(b"--"):
                    del buffer[:2]
                    state = "done"
                    break
                if not buffer.startswith(b"\r\n"):
                    raise HTTPException(status_code=422, detail="MEDIA_INVALID")
                del buffer[:2]
                state = "headers"
            else:
                break
    if state == "body":
        drain_body(final=True)
        state = "done"
    if state != "done":
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    files = [part for part in parts if part.filename is not None and part.name == "file"]
    names = [part.name for part in parts]
    if len(files) != 1 or len(names) != len(set(names)) or any(part.name not in {"file", "alt_text", "position"} for part in parts):
        for part in files:
            if part.path:
                part.path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    return files[0], {part.name: part.value for part in parts if part.filename is None}


def _storage(request: Request) -> LocalMediaStorage:
    root = Path(getattr(request.app.state.settings, "media_storage_root", Path("var/media")))
    return LocalMediaStorage(root)


@public_router.get("/media/{storage_key:path}", include_in_schema=False)
def public_media(storage_key: str, request: Request, session: Session = Depends(database_session, scope="function")) -> FileResponse:
    """Serve only a clean DB-backed server derivative, never quarantine bytes."""
    row = session.scalar(select(ProductMedia).where(ProductMedia.storage_key == storage_key, ProductMedia.scan_state == "clean"))
    if row is None:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    storage = _storage(request)
    try:
        path = MediaService(session, storage)._clean_path(row.storage_key)
    except HTTPException:
        raise HTTPException(status_code=404, detail="NOT_FOUND") from None
    if not path.is_file() or path.is_symlink():
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    content_type = row.metadata_json.get("content_type") if isinstance(row.metadata_json, dict) else None
    expected_content_type = "video/mp4" if row.media_type == "video" else "image/webp"
    if content_type != expected_content_type:
        raise HTTPException(status_code=404, detail="NOT_FOUND")
    return FileResponse(path, media_type=expected_content_type, headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "public, max-age=3600"})


@router.post("/products/{product_id}/media", response_model=MediaDTO, status_code=201, openapi_extra={"requestBody": {"required": True, "content": {"multipart/form-data": {"schema": {"type": "object", "required": ["file"], "properties": {"file": {"type": "string", "format": "binary"}, "alt_text": {"type": "string", "maxLength": 500}, "position": {"type": "integer", "minimum": 0}}}}}}}, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "Stale product version or CAPABILITY_DISABLED decoder gate"}})
async def create_media(product_id: UUID, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), version: int = Depends(admin_if_match, scope="function"), session: Session = Depends(database_session, scope="function")) -> MediaDTO:
    file_part, fields = await _parse_multipart(request)
    temp_path = file_part.path
    if temp_path is None:
        raise HTTPException(status_code=422, detail="MEDIA_INVALID")
    try:
        try:
            metadata = MediaUploadMetadata.model_validate({"alt_text": fields.get("alt_text", b"").decode("utf-8"), "position": int(fields.get("position", b"0"))})
        except (UnicodeError, ValueError, ValidationError) as exc:
            raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc
        suffix = Path(file_part.filename or "").suffix.lower()
        service = MediaService(session, _storage(request))
        with temp_path.open("rb") as source:
            if suffix == ".mp4" and file_part.content_type.lower().strip() == "video/mp4":
                if not getattr(request.app.state, "video_runtime_available", False):
                    raise HTTPException(status_code=409, detail="CAPABILITY_DISABLED")
                result = service.create_video(
                    admin=admin, product_id=product_id, expected_version=version,
                    source=source, filename=file_part.filename or "",
                    declared_content_type=file_part.content_type, alt_text=metadata.alt_text,
                    position=metadata.position, trace_id=getattr(request.state, "trace_id", None),
                    ffmpeg_binary=getattr(request.app.state.settings, "ffmpeg_binary", "ffmpeg"),
                    ffprobe_binary=getattr(request.app.state.settings, "ffprobe_binary", "ffprobe"),
                    timeout_seconds=getattr(request.app.state.settings, "video_processing_timeout_seconds", 30.0),
                )
            elif suffix in {".mp4", ".mov", ".webm", ".avi"} or file_part.content_type.lower().startswith("video/"):
                raise HTTPException(status_code=422, detail="MEDIA_INVALID")
            else:
                result = service.create_image(
                    admin=admin, product_id=product_id, expected_version=version,
                    source=source, filename=file_part.filename or "",
                    declared_content_type=file_part.content_type, alt_text=metadata.alt_text,
                    position=metadata.position, trace_id=getattr(request.state, "trace_id", None),
                )
        response.headers["ETag"] = f'"{version + 1}"'
        response.headers["X-Content-Type-Options"] = "nosniff"
        return result
    finally:
        temp_path.unlink(missing_ok=True)


@router.delete("/products/{product_id}/media/{media_id}", status_code=204, responses={401: {"description": "Admin session required"}, 403: {"description": "Permission or CSRF rejected"}, 409: {"description": "Stale product version"}})
def delete_media(product_id: UUID, media_id: UUID, request: Request, response: Response, admin: AdminPrincipal = Depends(admin_dependency("catalog.write", mutation=True)), version: int = Depends(admin_if_match, scope="function"), session: Session = Depends(database_session, scope="function")) -> Response:
    MediaService(session, _storage(request)).delete_media(admin=admin, product_id=product_id, media_id=media_id, expected_version=version, trace_id=getattr(request.state, "trace_id", None))
    response.headers["ETag"] = f'"{version + 1}"'
    # Returning the injected Response bypasses FastAPI's decorator status
    # default, so set the actual HTTP status explicitly. Without this the
    # delete commits but the client receives a malformed/failed response.
    response.status_code = 204
    return response
