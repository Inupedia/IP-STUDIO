"""Validate local Codex image output before it can reach the asset store."""

from dataclasses import dataclass
from pathlib import Path

from app.storage.local_blobs import AssetValidationError, ImageInfo, inspect_image

MAX_GENERATED_IMAGE_BYTES = 25 * 1024 * 1024
MAX_GENERATED_IMAGE_PIXELS = 40_000_000


class ImageResultError(Exception):
    pass


@dataclass(frozen=True)
class ValidatedImage:
    path: Path
    image: ImageInfo


def _mime_from_magic(data: bytes) -> str | None:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    return None


def validate_image_result(
    path: Path,
    allowed_dir: Path,
    *,
    max_bytes: int = MAX_GENERATED_IMAGE_BYTES,
    max_pixels: int = MAX_GENERATED_IMAGE_PIXELS,
) -> ValidatedImage:
    try:
        root = allowed_dir.resolve(strict=True)
    except OSError as error:
        raise ImageResultError("The allowed Codex output directory is unavailable") from error
    if not root.is_dir():
        raise ImageResultError("The allowed Codex output path is not a directory")

    candidate = path if path.is_absolute() else root / path
    if candidate.is_symlink():
        raise ImageResultError("Symlinked Codex output is not accepted")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as error:
        raise ImageResultError("Codex did not produce an image file") from error
    if not resolved.is_relative_to(root):
        raise ImageResultError("Codex image path escapes the allowed output directory")
    if not resolved.is_file():
        raise ImageResultError("Codex output is not a regular image file")

    try:
        size = resolved.stat().st_size
        if size <= 0 or size > max_bytes:
            raise ImageResultError("Codex image size is outside the allowed limit")
        data = resolved.read_bytes()
    except OSError as error:
        raise ImageResultError("Codex image file could not be read") from error
    mime = _mime_from_magic(data)
    if mime is None:
        raise ImageResultError("Codex output is not PNG or JPEG by file signature")
    try:
        image = inspect_image(data, mime, max_bytes, max_pixels)
    except AssetValidationError as error:
        raise ImageResultError(str(error)) from error
    return ValidatedImage(path=resolved, image=image)
