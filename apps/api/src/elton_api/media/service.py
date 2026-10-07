"""Admin-only product media commands."""
from __future__ import annotations

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.orm import Session

from elton_api.admin.auth import AdminPrincipal
from elton_api.media.image_processor import MediaValidationError, decode_and_reencode, validate_image
from elton_api.media.local_storage import LocalMediaStorage, QuarantinedMedia
from elton_api.media.schemas import MediaDTO
from elton_api.media.video_processor import MAX_VIDEO_BYTES, VideoValidationError, transcode_and_reencode
from elton_database.models.catalog import Product, ProductMedia
from elton_database.repositories.admin import AdminRepository


_ROLLBACK_CLEANUP = "_elton_media_rollback_cleanup"
_COMMIT_CLEANUP = "_elton_media_commit_cleanup"
_HOOKS_INSTALLED = "_elton_media_storage_hooks"


def _install_storage_hooks(session: Session) -> None:
    """Make filesystem cleanup follow the surrounding DB transaction."""
    if not hasattr(session, "info") or session.info.get(_HOOKS_INSTALLED):
        return

    def after_rollback(current: Session) -> None:
        for storage, path in current.info.pop(_ROLLBACK_CLEANUP, []):
            storage.cleanup(path)
        current.info.pop(_COMMIT_CLEANUP, None)

    def after_commit(current: Session) -> None:
        for storage, path in current.info.pop(_COMMIT_CLEANUP, []):
            storage.cleanup(path)
        current.info.pop(_ROLLBACK_CLEANUP, None)

    event.listen(session, "after_rollback", after_rollback)
    event.listen(session, "after_commit", after_commit)
    session.info[_HOOKS_INSTALLED] = True


def _defer_rollback_cleanup(session: Session, storage: LocalMediaStorage, path: Path) -> None:
    _install_storage_hooks(session)
    if hasattr(session, "info"):
        session.info.setdefault(_ROLLBACK_CLEANUP, []).append((storage, path))


def _defer_commit_cleanup(session: Session, storage: LocalMediaStorage, path: Path) -> None:
    _install_storage_hooks(session)
    if hasattr(session, "info"):
        session.info.setdefault(_COMMIT_CLEANUP, []).append((storage, path))


class MediaService:
    def __init__(self, session: Session, storage: LocalMediaStorage):
        self.session = session
        self.storage = storage

    def create_image(
        self,
        *,
        admin: AdminPrincipal,
        product_id: UUID,
        expected_version: int,
        source,
        filename: str,
        declared_content_type: str,
        alt_text: str,
        position: int,
        trace_id: str | None,
    ) -> MediaDTO:
        quarantine: QuarantinedMedia | None = None
        published: Path | None = None
        derivative: Path | None = None
        try:
            try:
                quarantine = self.storage.quarantine_stream(source)
            except MediaValidationError as exc:
                raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc
            try:
                validated = validate_image(quarantine.path, declared_content_type=declared_content_type, filename=filename)
            except MediaValidationError as exc:
                raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc

            product = self.session.scalar(select(Product).where(Product.id == product_id).with_for_update())
            if product is None:
                raise HTTPException(status_code=404, detail="NOT_FOUND")
            if product.version != expected_version:
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT")

            derivative = quarantine.path.with_suffix(".decoded")
            validated = decode_and_reencode(quarantine.path, derivative)
            storage_key, published = self.storage.publish(quarantine, validated, derivative)
            _defer_rollback_cleanup(self.session, self.storage, published)
            row = ProductMedia(
                id=uuid4(),
                product_id=product.id,
                storage_key=storage_key,
                media_type="image",
                scan_state="clean",
                position=position,
                alt_text=alt_text,
                metadata_json={
                    "content_type": validated.content_type,
                    "width": validated.width,
                    "height": validated.height,
                    "byte_size": validated.byte_size,
                    "sha256": quarantine.sha256,
                },
            )
            self.session.add(row)
            product.version += 1
            AdminRepository(self.session).audit(
                actor_id=admin.id,
                action="catalog.media.create",
                entity_type="product_media",
                entity_id=row.id,
                change_summary={"product_id": str(product.id), "media_type": "image", "position": position},
                trace_id=trace_id,
            )
            self.session.flush()
            return MediaDTO(id=row.id, type="image", url=f"/api/v1/media/{storage_key}", alt_text=alt_text, position=position)
        except Exception:
            if quarantine is not None:
                self.storage.cleanup(quarantine)
            if derivative is not None:
                self.storage.cleanup(derivative)
            if published is not None:
                self.storage.cleanup(published)
            raise

    def delete_media(
        self,
        *,
        admin: AdminPrincipal,
        product_id: UUID,
        media_id: UUID,
        expected_version: int,
        trace_id: str | None,
    ) -> None:
        product = self.session.scalar(select(Product).where(Product.id == product_id).with_for_update())
        if product is None:
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        if product.version != expected_version:
            raise HTTPException(status_code=409, detail="VERSION_CONFLICT")
        row = self.session.scalar(select(ProductMedia).where(ProductMedia.id == media_id, ProductMedia.product_id == product_id).with_for_update())
        if row is None or row.scan_state != "clean":
            raise HTTPException(status_code=404, detail="NOT_FOUND")
        path = self._clean_path(row.storage_key)
        self.session.delete(row)
        product.version += 1
        AdminRepository(self.session).audit(
            actor_id=admin.id,
            action="catalog.media.delete",
            entity_type="product_media",
            entity_id=media_id,
            change_summary={"product_id": str(product.id)},
            trace_id=trace_id,
        )
        self.session.flush()
        _defer_commit_cleanup(self.session, self.storage, path)

    def create_video(
        self,
        *,
        admin: AdminPrincipal,
        product_id: UUID,
        expected_version: int,
        source,
        filename: str,
        declared_content_type: str,
        alt_text: str,
        position: int,
        trace_id: str | None,
        ffmpeg_binary: str = "ffmpeg",
        ffprobe_binary: str = "ffprobe",
        timeout_seconds: float = 30.0,
    ) -> MediaDTO:
        """Validate, transcode and publish one clean product video."""
        quarantine: QuarantinedMedia | None = None
        published: Path | None = None
        derivative: Path | None = None
        try:
            try:
                quarantine = self.storage.quarantine_stream(source, limit=MAX_VIDEO_BYTES)
            except MediaValidationError as exc:
                raise HTTPException(status_code=422, detail="MEDIA_INVALID") from exc
            product = self.session.scalar(select(Product).where(Product.id == product_id).with_for_update())
            if product is None:
                raise HTTPException(status_code=404, detail="NOT_FOUND")
            if product.version != expected_version:
                raise HTTPException(status_code=409, detail="VERSION_CONFLICT")
            derivative = quarantine.path.with_suffix(".decoded.mp4")
            try:
                validated = transcode_and_reencode(
                    quarantine.path,
                    derivative,
                    declared_content_type=declared_content_type,
                    filename=filename,
                    ffmpeg_binary=ffmpeg_binary,
                    ffprobe_binary=ffprobe_binary,
                    timeout_seconds=timeout_seconds,
                )
            except VideoValidationError as exc:
                # A missing or unusable trusted toolchain is a capability gate,
                # while a decoded file that violates policy is invalid input.
                capability_error = any(token in str(exc).lower() for token in ("unavailable", "timed out"))
                raise HTTPException(status_code=409 if capability_error else 422, detail="CAPABILITY_DISABLED" if capability_error else "MEDIA_INVALID") from exc
            storage_key, published = self.storage.publish(quarantine, validated, derivative)
            _defer_rollback_cleanup(self.session, self.storage, published)
            row = ProductMedia(
                id=uuid4(), product_id=product.id, storage_key=storage_key,
                media_type="video", scan_state="clean", position=position,
                alt_text=alt_text,
                metadata_json={
                    "content_type": validated.content_type,
                    "width": validated.width,
                    "height": validated.height,
                    "duration_seconds": validated.duration_seconds,
                    "byte_size": validated.byte_size,
                    "video_codec": validated.video_codec,
                    "audio_codec": validated.audio_codec,
                    "sha256": quarantine.sha256,
                },
            )
            self.session.add(row)
            product.version += 1
            AdminRepository(self.session).audit(
                actor_id=admin.id, action="catalog.media.create", entity_type="product_media",
                entity_id=row.id,
                change_summary={"product_id": str(product.id), "media_type": "video", "position": position},
                trace_id=trace_id,
            )
            self.session.flush()
            return MediaDTO(id=row.id, type="video", url=f"/api/v1/media/{storage_key}", alt_text=alt_text, position=position)
        except Exception:
            if quarantine is not None:
                self.storage.cleanup(quarantine)
            if derivative is not None:
                self.storage.cleanup(derivative)
            if published is not None:
                self.storage.cleanup(published)
            raise

    def _clean_path(self, storage_key: str) -> Path:
        prefix, separator, name = storage_key.partition("/")
        if prefix != "clean" or not separator or not self.storage._safe_name(name):
            raise HTTPException(status_code=503, detail="STORAGE_TEMPORARILY_UNAVAILABLE")
        path = self.storage.clean / name
        if not self.storage._inside(path, self.storage.clean):
            raise HTTPException(status_code=503, detail="STORAGE_TEMPORARILY_UNAVAILABLE")
        return path
