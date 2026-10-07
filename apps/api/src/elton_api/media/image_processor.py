"""Bounded, signature-aware raster image validation.

This module intentionally does not use a browser or a permissive MIME guesser.
It validates the container structure and dimensions before a file can leave
quarantine. A real decoder can be added behind the same interface later; until
then unsupported or malformed containers fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError


MAX_BYTES = 10 * 1024 * 1024
MAX_DIMENSION = 8192
MAX_PIXELS = 40_000_000
MAX_DECODED_BYTES = 128 * 1024 * 1024
CHUNK_SIZE = 64 * 1024

_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
_HTML_MARKERS = re.compile(rb"<\s*(?:!doctype|html|script|svg|iframe|object|embed)\b|<\?xml", re.I)


class MediaValidationError(ValueError):
    """Input is not an accepted image container or exceeds a declared limit."""


@dataclass(frozen=True)
class ValidatedImage:
    content_type: str
    extension: str
    width: int
    height: int
    byte_size: int
    decoder_verified: bool = False


def _bad(message: str) -> MediaValidationError:
    return MediaValidationError(message)


def read_limited(source: BinaryIO, destination: BinaryIO, *, limit: int = MAX_BYTES) -> tuple[int, str]:
    """Copy a stream with a hard byte limit and return size plus SHA-256."""
    import hashlib

    digest = hashlib.sha256()
    size = 0
    while True:
        chunk = source.read(CHUNK_SIZE)
        if not chunk:
            break
        if not isinstance(chunk, (bytes, bytearray, memoryview)):
            raise _bad("media stream did not return bytes")
        size += len(chunk)
        if size > limit:
            raise _bad("media exceeds the byte limit")
        destination.write(chunk)
        digest.update(chunk)
    return size, digest.hexdigest()


def _validate_dimensions(width: int, height: int) -> None:
    if width <= 0 or height <= 0 or width > MAX_DIMENSION or height > MAX_DIMENSION:
        raise _bad("image dimensions exceed the limit")
    if width * height > MAX_PIXELS:
        raise _bad("image pixel count exceeds the limit")


def _parse_png(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\x89PNG\r\n\x1a\n"):
        raise _bad("invalid PNG signature")
    import struct
    import zlib

    offset = 8
    width = height = None
    decoded_size = None
    idat = bytearray()
    saw_iend = False
    while offset < len(data):
        if len(data) - offset < 12:
            raise _bad("truncated PNG chunk")
        length = struct.unpack_from(">I", data, offset)[0]
        chunk_start = offset + 4
        chunk_end = chunk_start + 4 + length + 4
        if chunk_end > len(data):
            raise _bad("truncated PNG chunk")
        kind = data[chunk_start:chunk_start + 4]
        if not re.fullmatch(rb"[A-Za-z]{4}", kind):
            raise _bad("invalid PNG chunk name")
        payload = data[chunk_start + 4:chunk_start + 4 + length]
        crc = struct.unpack_from(">I", data, chunk_start + 4 + length)[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != crc:
            raise _bad("invalid PNG CRC")
        if kind == b"IHDR":
            if width is not None or length != 13:
                raise _bad("invalid PNG IHDR")
            width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(">IIBBBBB", payload)
            if compression != 0 or filtering != 0 or interlace != 0:
                raise _bad("unsupported PNG encoding")
            allowed_depths = {0: {1, 2, 4, 8, 16}, 2: {8, 16}, 3: {1, 2, 4, 8}, 4: {8, 16}, 6: {8, 16}}
            if color_type not in allowed_depths or bit_depth not in allowed_depths[color_type]:
                raise _bad("unsupported PNG color format")
            _validate_dimensions(width, height)
            channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
            row_bytes = (width * channels * bit_depth + 7) // 8
            decoded_size = (row_bytes + 1) * height
            if decoded_size > MAX_DECODED_BYTES:
                raise _bad("PNG decoded payload exceeds the safety limit")
        elif kind == b"IDAT":
            idat.extend(payload)
            if len(idat) > MAX_BYTES:
                raise _bad("PNG compressed payload exceeds the byte limit")
        elif kind == b"IEND":
            if length != 0 or width is None or not idat:
                raise _bad("incomplete PNG")
            saw_iend = True
            offset = chunk_end
            break
        offset = chunk_end
    if not saw_iend or offset != len(data) or width is None or height is None:
        raise _bad("PNG must end at IEND")
    # Bound zlib expansion before accepting compressed scanlines. The expected
    # payload is calculated from IHDR and includes one filter byte per row.
    if decoded_size is None:
        raise _bad("PNG dimensions are missing")
    try:
        decompressor = zlib.decompressobj()
        expanded = decompressor.decompress(bytes(idat), decoded_size + 1)
        if len(expanded) != decoded_size or not decompressor.eof or decompressor.unused_data:
            raise _bad("PNG decompression exceeds the safety limit")
    except zlib.error as exc:
        raise _bad("invalid PNG compressed payload") from exc
    return width, height


def _parse_jpeg(data: bytes) -> tuple[int, int]:
    if not data.startswith(b"\xff\xd8"):
        raise _bad("invalid JPEG signature")
    offset = 2
    width = height = None
    saw_eoi = False
    sof_markers = set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0))
    while offset < len(data):
        if data[offset] != 0xFF:
            # Entropy-coded bytes are only allowed after SOS. Find EOI there.
            raise _bad("invalid JPEG marker sequence")
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            raise _bad("truncated JPEG marker")
        marker = data[offset]
        offset += 1
        if marker == 0xD9:
            saw_eoi = True
            break
        if marker == 0xDA:
            if offset + 2 > len(data):
                raise _bad("truncated JPEG scan")
            length = int.from_bytes(data[offset:offset + 2], "big")
            if length < 2 or offset + length > len(data):
                raise _bad("invalid JPEG scan")
            offset += length
            # Scan data ends at an unescaped FF marker. Stuffed FF00 and
            # restart markers remain within the scan.
            while offset < len(data):
                if data[offset] != 0xFF:
                    offset += 1
                    continue
                if offset + 1 >= len(data):
                    raise _bad("truncated JPEG scan")
                nxt = data[offset + 1]
                if nxt == 0x00 or 0xD0 <= nxt <= 0xD7:
                    offset += 2
                    continue
                break
            continue
        if marker == 0xD8 or marker == 0x01 or 0xD0 <= marker <= 0xD7:
            # SOI, TEM and restart markers do not carry a segment.
            continue
        if offset + 2 > len(data):
            raise _bad("truncated JPEG segment")
        length = int.from_bytes(data[offset:offset + 2], "big")
        if length < 2 or offset + length > len(data):
            raise _bad("invalid JPEG segment")
        if marker in sof_markers:
            if length < 7:
                raise _bad("invalid JPEG frame")
            height = int.from_bytes(data[offset + 3:offset + 5], "big")
            width = int.from_bytes(data[offset + 5:offset + 7], "big")
            _validate_dimensions(width, height)
        offset += length
    if not saw_eoi or offset != len(data) or width is None or height is None:
        raise _bad("JPEG must contain dimensions and terminate at EOI")
    return width, height


def _parse_webp(data: bytes) -> tuple[int, int]:
    if len(data) < 20 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise _bad("invalid WebP signature")
    declared = int.from_bytes(data[4:8], "little")
    if declared != len(data) - 8:
        raise _bad("WebP RIFF length does not match the file")
    offset = 12
    width = height = None
    while offset < len(data):
        if len(data) - offset < 8:
            raise _bad("truncated WebP chunk")
        kind = data[offset:offset + 4]
        length = int.from_bytes(data[offset + 4:offset + 8], "little")
        payload_start, payload_end = offset + 8, offset + 8 + length
        padded_end = payload_end + (length & 1)
        if padded_end > len(data):
            raise _bad("truncated WebP chunk")
        payload = data[payload_start:payload_end]
        if kind == b"VP8X":
            if length < 10 or payload[0] & 0x01:
                raise _bad("unsupported WebP VP8X features")
            width = 1 + int.from_bytes(payload[4:7], "little")
            height = 1 + int.from_bytes(payload[7:10], "little")
        elif kind == b"VP8 " and length >= 30 and payload[3:6] == b"\x9d\x01\x2a":
            width = int.from_bytes(payload[6:8], "little") & 0x3FFF
            height = int.from_bytes(payload[8:10], "little") & 0x3FFF
        elif kind == b"VP8L" and length >= 5 and payload[0] == 0x2F:
            bits = int.from_bytes(payload[1:5], "little")
            width = (bits & 0x3FFF) + 1
            height = ((bits >> 14) & 0x3FFF) + 1
        offset = padded_end
    if offset != len(data) or width is None or height is None:
        raise _bad("WebP dimensions are missing")
    _validate_dimensions(width, height)
    return width, height


def validate_image(path: Path, *, declared_content_type: str, filename: str) -> ValidatedImage:
    """Validate a quarantined file and return trusted metadata."""
    data = path.read_bytes()
    if not data or len(data) > MAX_BYTES:
        raise _bad("media exceeds the byte limit")
    ext = Path(filename).suffix.lower()
    if not filename or Path(filename).name != filename or "/" in filename or "\\" in filename:
        raise _bad("filename traversal is not allowed")
    expected = _CONTENT_TYPES.get(ext)
    if expected is None or declared_content_type.lower().strip() != expected:
        raise _bad("MIME type and extension do not agree")
    if _HTML_MARKERS.search(data):
        raise _bad("active or markup content is not an image")
    if data.startswith(b"\xff\xd8\xff"):
        content_type, width, height = "image/jpeg", *_parse_jpeg(data)
    elif data.startswith(b"\x89PNG\r\n\x1a\n"):
        content_type, width, height = "image/png", *_parse_png(data)
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        content_type, width, height = "image/webp", *_parse_webp(data)
    else:
        raise _bad("unsupported or spoofed image signature")
    if content_type != expected:
        raise _bad("MIME type and signature do not agree")
    return ValidatedImage(content_type, ext, width, height, len(data))


def decode_and_reencode(path: Path, destination: Path) -> ValidatedImage:
    """Fully decode one still image and write a metadata-free WebP derivative.

    The quarantined source is never promoted. Pillow decodes pixel data before a
    fresh server-selected container is produced, which drops EXIF, ICC, XMP and
    source chunks. Animated content is deliberately rejected pending a separate
    video/animation policy.
    """
    try:
        with Image.open(path) as source:
            if getattr(source, "n_frames", 1) != 1:
                raise _bad("animated images are not accepted")
            source.load()
            image = ImageOps.exif_transpose(source)
            _validate_dimensions(*image.size)
            if image.width * image.height * 4 > MAX_DECODED_BYTES:
                raise _bad("decoded image exceeds the safety limit")
            if image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "A" in image.getbands() else "RGB")
            # Saving a newly created file and supplying no metadata removes all
            # source metadata. A deterministic WebP extension also prevents
            # serving source-defined content types.
            image.save(destination, format="WEBP", quality=90, method=6, exif=b"", icc_profile=None, xmp=b"")
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as exc:
        destination.unlink(missing_ok=True)
        raise _bad("trusted decoder rejected image") from exc
    byte_size = destination.stat().st_size
    if not byte_size or byte_size > MAX_BYTES:
        destination.unlink(missing_ok=True)
        raise _bad("encoded derivative exceeds the byte limit")
    return ValidatedImage("image/webp", ".webp", image.width, image.height, byte_size, decoder_verified=True)
