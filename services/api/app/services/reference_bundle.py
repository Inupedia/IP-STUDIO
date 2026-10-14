import hashlib
import json
from io import BytesIO
from pathlib import Path
from uuid import UUID
from zipfile import ZIP_DEFLATED, ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.assets import AssetVersion, Blob
from app.services.generation import ResourceConflict, get_generation_task
from app.storage.local_blobs import resolve_blob_path

ASSET_EXTENSIONS = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}
MAX_REFERENCE_BUNDLE_BYTES = 100 * 1024 * 1024


def create_reference_bundle(
    session: Session,
    workspace_id: UUID,
    task_id: UUID,
    storage_dir: Path,
) -> bytes:
    task = get_generation_task(session, workspace_id, task_id)
    expected_assets = {
        str(reference["version_id"]): reference
        for reference in task.reference_snapshot
        if reference["kind"] == "asset_version"
    }
    version_ids = [UUID(version_id) for version_id in expected_assets]
    rows = session.execute(
        select(AssetVersion, Blob)
        .join(Blob, Blob.id == AssetVersion.blob_id)
        .where(AssetVersion.id.in_(version_ids))
    ).all() if version_ids else []
    blobs_by_version = {str(version.id): (version, blob) for version, blob in rows}

    archive_buffer = BytesIO()
    manifest_assets: list[dict[str, object]] = []
    uncompressed_bytes = 0
    with ZipFile(archive_buffer, mode="w", compression=ZIP_DEFLATED) as archive:
        for version_id, snapshot in expected_assets.items():
            version_blob = blobs_by_version.get(version_id)
            if version_blob is None:
                raise ResourceConflict("A frozen reference asset is no longer available")
            version, blob = version_blob
            if (
                blob.sha256 != snapshot["sha256"]
                or blob.mime != snapshot["mime"]
                or blob.byte_size != snapshot["byte_size"]
            ):
                raise ResourceConflict("A reference asset no longer matches its frozen snapshot")
            uncompressed_bytes += blob.byte_size
            if uncompressed_bytes > MAX_REFERENCE_BUNDLE_BYTES:
                raise ResourceConflict("Reference package exceeds the 100 MiB total size limit")
            try:
                path = resolve_blob_path(storage_dir, blob.storage_key)
                content = path.read_bytes()
            except (OSError, ValueError) as error:
                raise ResourceConflict("A stored reference blob is no longer available") from error
            if len(content) != blob.byte_size or hashlib.sha256(content).hexdigest() != blob.sha256:
                raise ResourceConflict("A stored reference blob failed its integrity check")
            extension = ASSET_EXTENSIONS.get(blob.mime)
            if extension is None:
                raise ResourceConflict("A frozen reference uses an unsupported image format")
            archive_path = f"assets/{version.id}.{extension}"
            archive.writestr(archive_path, content)
            manifest_assets.append({**snapshot, "path": archive_path})

        locked_version_ids = {
            "character": [
                reference["version_id"]
                for reference in task.reference_snapshot
                if reference["kind"] == "character_version"
            ],
            "style": [
                reference["version_id"]
                for reference in task.reference_snapshot
                if reference["kind"] == "style_version"
            ],
            "asset": [
                reference["version_id"]
                for reference in task.reference_snapshot
                if reference["kind"] == "asset_version"
            ],
        }
        manifest = {
            "schema_version": "1.0",
            "task_id": str(task.id),
            "episode_id": str(task.episode_id),
            "script_revision_id": str(task.script_revision_id),
            "script_revision_no": task.script_revision_no,
            "panel_id": str(task.panel_id),
            "mode": task.mode,
            "prompt_snapshot": task.prompt_snapshot,
            "locked_version_ids": locked_version_ids,
            "references": task.reference_snapshot,
            "assets": manifest_assets,
        }
        archive.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return archive_buffer.getvalue()
