"""Local quarantine/clean storage with server-selected UUID keys."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import select

from elton_database.models.catalog import ProductMedia
from .image_processor import MAX_BYTES, MediaValidationError, ValidatedImage, read_limited


@dataclass(frozen=True)
class QuarantinedMedia:
    path: Path
    token: UUID
    byte_size: int
    sha256: str


class LocalMediaStorage:
    """Filesystem storage whose root is never mounted as a public web root."""

    def __init__(self, root: Path):
        self.root = Path(root).expanduser().resolve()
        self.quarantine = self.root / "quarantine"
        self.clean = self.root / "clean"
        self.quarantine.mkdir(parents=True, exist_ok=True)
        self.clean.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _uuid_name(token: UUID, extension: str) -> str:
        if extension not in {".jpg", ".jpeg", ".png", ".webp", ".mp4"}:
            raise ValueError("unsupported media extension")
        return f"{token}{extension}"

    def quarantine_stream(self, source, *, limit: int = MAX_BYTES) -> QuarantinedMedia:
        token = uuid4()
        path = self.quarantine / str(token)
        try:
            with path.open("xb") as target:
                size, digest = read_limited(source, target, limit=limit)
            return QuarantinedMedia(path, token, size, digest)
        except Exception:
            self.safe_unlink(path)
            raise

    def publish(self, item: QuarantinedMedia, validated: ValidatedImage, derivative: Path) -> tuple[str, Path]:
        if not validated.decoder_verified:
            raise ValueError("trusted decoder is required before clean publication")
        if item.path.parent != self.quarantine or not item.path.exists() or derivative.parent != self.quarantine or not derivative.exists():
            raise ValueError("quarantine item is not owned by this storage")
        key = f"clean/{self._uuid_name(item.token, validated.extension)}"
        destination = self.clean / self._uuid_name(item.token, validated.extension)
        destination.parent.mkdir(parents=True, exist_ok=True)
        os.replace(derivative, destination)
        self.safe_unlink(item.path)
        return key, destination

    def cleanup(self, item: QuarantinedMedia | Path | None) -> None:
        if item is None:
            return
        path = item.path if isinstance(item, QuarantinedMedia) else Path(item)
        if self._inside(path, self.quarantine) or self._inside(path, self.clean):
            self.safe_unlink(path)

    def cleanup_orphans(self, session, *, older_than: timedelta = timedelta(hours=1)) -> int:
        """Remove only stale files with no live clean DB reference.

        A database failure is deliberately propagated: an unavailable DB must
        never turn a live clean file into a deletion candidate.
        """
        live_keys = set(session.scalars(select(ProductMedia.storage_key).where(ProductMedia.scan_state == "clean")))
        cutoff = datetime.now(timezone.utc) - older_than
        removed = 0
        for folder in (self.quarantine, self.clean):
            for path in folder.iterdir():
                if not path.is_file() or path.is_symlink():
                    continue
                modified = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
                key = f"clean/{path.name}" if folder == self.clean else None
                if modified < cutoff and self._safe_name(path.name) and (key is None or key not in live_keys):
                    self.safe_unlink(path)
                    removed += 1
        return removed

    @staticmethod
    def safe_unlink(path: Path) -> None:
        try:
            if path.is_symlink() or path.is_file():
                path.unlink()
        except OSError:
            pass

    @staticmethod
    def _safe_name(name: str) -> bool:
        stem, suffix = os.path.splitext(name)
        try:
            UUID(stem)
        except ValueError:
            return False
        return suffix in {"", ".jpg", ".jpeg", ".png", ".webp", ".mp4"}

    @staticmethod
    def _inside(path: Path, parent: Path) -> bool:
        try:
            path.resolve().relative_to(parent.resolve())
        except ValueError:
            return False
        return True
