from __future__ import annotations

import hashlib
import os
import re
import tempfile
import warnings
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

MIME_BY_FORMAT = {"PNG": "image/png", "JPEG": "image/jpeg", "WEBP": "image/webp"}
MIME_BY_MAGIC = {b"\x89PNG\r\n\x1a\n": "image/png"}


class AssetValidationError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


@dataclass(frozen=True)
class ImageInfo:
    sha256: str
    mime: str
    byte_size: int
    width: int
    height: int
    alpha: bool


def _mime_from_magic(data: bytes) -> str | None:
    for signature, mime in MIME_BY_MAGIC.items():
        if data.startswith(signature):
            return mime
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def inspect_image(data: bytes, declared_mime: str, max_bytes: int, max_pixels: int) -> ImageInfo:
    if not data:
        raise AssetValidationError("The uploaded image is empty", 422)
    if len(data) > max_bytes:
        raise AssetValidationError("The uploaded image exceeds the file size limit", 413)

    normalized_mime = declared_mime.split(";", 1)[0].strip().casefold()
    detected_mime = _mime_from_magic(data)
    if detected_mime is None or detected_mime != normalized_mime:
        raise AssetValidationError("The file contents do not match a supported image MIME type", 415)

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(data)) as image:
                image_format = image.format
                width, height = image.size
                if image_format not in MIME_BY_FORMAT or MIME_BY_FORMAT[image_format] != detected_mime:
                    raise AssetValidationError("The image format is not supported", 415)
                if width <= 0 or height <= 0 or width * height > max_pixels:
                    raise AssetValidationError("The image exceeds the pixel dimension limit", 413)
                image.verify()

            with Image.open(BytesIO(data)) as decoded:
                decoded.load()
                has_alpha = decoded.mode in {"RGBA", "LA", "PA"} or "transparency" in decoded.info
    except AssetValidationError:
        raise
    except (Image.DecompressionBombError, Image.DecompressionBombWarning) as error:
        raise AssetValidationError("The image exceeds the pixel dimension limit", 413) from error
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as error:
        raise AssetValidationError("The uploaded file is not a decodable image", 422) from error

    return ImageInfo(
        sha256=hashlib.sha256(data).hexdigest(),
        mime=detected_mime,
        byte_size=len(data),
        width=width,
        height=height,
        alpha=has_alpha,
    )


def storage_key_for_sha256(sha256: str) -> str:
    if not re.fullmatch(r"[0-9a-f]{64}", sha256):
        raise ValueError("Expected a lowercase SHA-256 digest")
    return f"{sha256[:2]}/{sha256}"


def resolve_blob_path(storage_dir: Path, storage_key: str) -> Path:
    match = re.fullmatch(r"([0-9a-f]{2})/([0-9a-f]{64})", storage_key)
    if match is None or match.group(1) != match.group(2)[:2]:
        raise ValueError("Invalid content-addressed storage key")
    root = storage_dir.resolve()
    path = (root / storage_key).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Blob path escapes the configured storage directory")
    return path


def put_blob(data: bytes, sha256: str, storage_dir: Path) -> str:
    """Atomically persist verified bytes under their SHA-256-derived key."""
    storage_key = storage_key_for_sha256(sha256)
    path = resolve_blob_path(storage_dir, storage_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Recheck after mkdir so a replaced prefix directory cannot redirect writes.
    path = resolve_blob_path(storage_dir, storage_key)
    if path.is_file() and hashlib.sha256(path.read_bytes()).hexdigest() == sha256:
        return storage_key

    descriptor, temporary_name = tempfile.mkstemp(prefix=".upload-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as temporary_file:
            temporary_file.write(data)
            temporary_file.flush()
            os.fsync(temporary_file.fileno())
        os.replace(temporary_name, path)
    except BaseException:
        Path(temporary_name).unlink(missing_ok=True)
        raise
    return storage_key
