from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
from io import BytesIO
import json
from pathlib import Path, PurePosixPath, PureWindowsPath
import stat
import tempfile
from typing import Any
from uuid import UUID, uuid4
import zipfile

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assets import Asset, AssetLink, AssetVersion, Blob
from app.models.bibles import Style, StyleVersion
from app.models.documents import DocumentRevision
from app.models.ip import IP
from app.models.story import Episode, Series
from app.models.templates import BrandTemplate, BrandTemplateVersion
from app.schemas.bibles import StyleBible
from app.schemas.canvas import CanvasDocument
from app.schemas.project_bundle import ProjectAssetSnapshot, ProjectManifest
from app.schemas.templates import BrandTemplateV1
from app.services.documents import ResourceConflict as DocumentConflict
from app.services.documents import ResourceNotFound as DocumentNotFound
from app.services.documents import save_document
from app.storage.local_blobs import (
    AssetValidationError,
    inspect_image,
    put_blob,
    resolve_blob_path,
)

MAX_BUNDLE_UPLOAD_BYTES = 250 * 1024 * 1024
MAX_BUNDLE_UNCOMPRESSED_BYTES = 200 * 1024 * 1024
MAX_BUNDLE_FILES = 502
MAX_MANIFEST_BYTES = 5 * 1024 * 1024
MIME_EXTENSION = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class ProjectBundleNotFound(Exception):
    pass


class ProjectBundleConflict(Exception):
    pass


class ProjectBundleValidationError(Exception):
    def __init__(self, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.status_code = status_code


def _hash_file(path: Path) -> str:
    with path.open("rb") as file:
        return hashlib.file_digest(file, "sha256").hexdigest()


def _referenced_document_assets(document: dict[str, Any]) -> set[UUID]:
    return {
        UUID(str(element["asset_version_id"]))
        for page in document["pages"]
        for panel in page["panels"]
        for element in panel["elements"]
        if element.get("type") in {"image", "sticker"}
    }


def _referenced_template_assets(template: dict[str, Any]) -> set[UUID]:
    return {
        UUID(str(element["asset_version_id"]))
        for element in template["locked_elements"]
        if element.get("asset_version_id")
    }


def _referenced_style_assets(bible: dict[str, Any]) -> set[UUID]:
    parsed = StyleBible.model_validate(bible)
    return set(parsed.example_asset_version_ids)


def _required_asset_version_ids(
    document: dict[str, Any], brand: dict[str, Any], styles: list[dict[str, Any]]
) -> set[UUID]:
    result = _referenced_document_assets(document) | _referenced_template_assets(brand)
    for style in styles:
        result.update(_referenced_style_assets(style["bible_json"]))
    return result


def _load_export_snapshots(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    revision_no: int,
) -> tuple[Episode, Series, IP, CanvasDocument, BrandTemplate, BrandTemplateVersion, list[tuple[Style, StyleVersion]]]:
    revision = session.scalar(
        select(DocumentRevision).where(
            DocumentRevision.episode_id == episode_id,
            DocumentRevision.workspace_id == workspace_id,
            DocumentRevision.revision_no == revision_no,
        )
    )
    if revision is None:
        raise ProjectBundleNotFound("Document revision not found")
    try:
        document = CanvasDocument.model_validate(revision.snapshot_json)
    except ValidationError as error:
        raise ProjectBundleConflict("Stored document revision is invalid") from error
    if document.episode_id != episode_id or document.revision != revision_no:
        raise ProjectBundleConflict("Document snapshot does not match the requested revision")

    row = session.execute(
        select(Episode, Series, IP)
        .join(Series, Series.id == Episode.series_id)
        .join(IP, IP.id == Series.ip_id)
        .where(
            Episode.id == episode_id,
            Episode.workspace_id == workspace_id,
            Series.workspace_id == workspace_id,
            IP.workspace_id == workspace_id,
        )
    ).first()
    if row is None:
        raise ProjectBundleNotFound("Episode not found")
    episode, series, ip = row

    brand_row = session.execute(
        select(BrandTemplate, BrandTemplateVersion)
        .join(BrandTemplateVersion, BrandTemplateVersion.brand_template_id == BrandTemplate.id)
        .where(
            BrandTemplateVersion.id == document.brand_template_version_id,
            BrandTemplate.workspace_id == workspace_id,
            BrandTemplate.ip_id == ip.id,
        )
    ).first()
    if brand_row is None or brand_row[1].status != "approved":
        raise ProjectBundleConflict("Document brand version is unavailable or not approved")
    brand_template, brand_version = brand_row
    BrandTemplateV1.model_validate(brand_version.template_json)

    style_version_ids = {
        version_id
        for version_id in (document.style_version_id, episode.default_style_version_id)
        if version_id is not None
    }
    style_snapshots: list[tuple[Style, StyleVersion]] = []
    if style_version_ids:
        style_rows = session.execute(
            select(Style, StyleVersion)
            .join(StyleVersion, StyleVersion.style_id == Style.id)
            .where(
                StyleVersion.id.in_(style_version_ids),
                Style.workspace_id == workspace_id,
                Style.ip_id == ip.id,
            )
        ).all()
        styles_found = {version.id for _style, version in style_rows}
        if styles_found != style_version_ids or any(version.status != "approved" for _style, version in style_rows):
            raise ProjectBundleConflict("Document style version is unavailable or not approved")
        for style, version in style_rows:
            StyleBible.model_validate(version.bible_json)
            style_snapshots.append((style, version))
    return episode, series, ip, document, brand_template, brand_version, style_snapshots


def export_project_bundle(
    session: Session,
    workspace_id: UUID,
    episode_id: UUID,
    revision_no: int,
    storage_dir: Path,
    max_asset_bytes: int,
    max_pixels: int,
) -> bytes:
    episode, series, ip, document_model, brand, brand_version, style_snapshots = _load_export_snapshots(
        session, workspace_id, episode_id, revision_no
    )
    document = document_model.model_dump(mode="json")
    brand_json = deepcopy(brand_version.template_json)
    styles = [
        {
            "style_id": str(style.id),
            "style_name": style.name,
            "version_id": str(version.id),
            "version_no": version.version_no,
            "approved_at": version.approved_at,
            "bible_json": version.bible_json,
        }
        for style, version in style_snapshots
    ]
    asset_ids = _required_asset_version_ids(document, brand_json, styles)
    if asset_ids:
        asset_rows = session.execute(
            select(Asset, AssetVersion, Blob)
            .join(AssetVersion, AssetVersion.asset_id == Asset.id)
            .join(Blob, Blob.id == AssetVersion.blob_id)
            .where(
                AssetVersion.id.in_(asset_ids),
                AssetVersion.workspace_id == workspace_id,
                Asset.workspace_id == workspace_id,
            )
        ).all()
    else:
        asset_rows = []
    found_ids = {version.id for _asset, version, _blob in asset_rows}
    if found_ids != asset_ids:
        raise ProjectBundleConflict("One or more referenced asset versions are missing")

    manifest_assets: list[dict[str, Any]] = []
    blob_files: dict[str, bytes] = {}
    for asset, version, blob in asset_rows:
        if asset.owner_ip_id != ip.id or version.status != "approved" or version.approved_at is None:
            raise ProjectBundleConflict("Only approved asset versions from this IP can be exported")
        if blob.byte_size > max_asset_bytes or blob.mime not in MIME_EXTENSION:
            raise ProjectBundleConflict("A referenced asset exceeds the supported export limits")
        path = resolve_blob_path(storage_dir, blob.storage_key)
        if not path.is_file() or path.stat().st_size != blob.byte_size or _hash_file(path) != blob.sha256:
            raise ProjectBundleConflict("A referenced asset Blob is missing or failed its SHA-256 check")
        data = path.read_bytes()
        try:
            image = inspect_image(data, blob.mime, max_asset_bytes, max_pixels)
        except AssetValidationError as error:
            raise ProjectBundleConflict("A referenced asset Blob is not a valid image") from error
        if (image.sha256, image.width, image.height, image.alpha) != (
            blob.sha256, version.width, version.height, version.alpha
        ):
            raise ProjectBundleConflict("Referenced asset metadata does not match its Blob")
        blob_path = f"blobs/{blob.sha256}.{MIME_EXTENSION[blob.mime]}"
        blob_files[blob_path] = data
        manifest_assets.append({
            "asset_id": str(asset.id),
            "asset_version_id": str(version.id),
            "version_no": version.version_no,
            "name": asset.name,
            "type": asset.type,
            "source_type": asset.source_type,
            "rights_note": asset.rights_note,
            "status": "approved",
            "width": version.width,
            "height": version.height,
            "alpha": version.alpha,
            "metadata_json": version.metadata_json,
            "approved_at": version.approved_at,
            "sha256": blob.sha256,
            "mime": blob.mime,
            "byte_size": blob.byte_size,
            "blob_path": blob_path,
        })
    if len(blob_files) > 500 or sum(map(len, blob_files.values())) > MAX_BUNDLE_UNCOMPRESSED_BYTES:
        raise ProjectBundleConflict("Project bundle exceeds the portable asset limit")

    if brand_version.approved_at is None or any(version.approved_at is None for _, version in style_snapshots):
        raise ProjectBundleConflict("Approved version timestamps are missing")
    manifest = ProjectManifest.model_validate({
        "schema_version": "1.0",
        "exported_at": datetime.now(timezone.utc),
        "source": {
            "workspace_id": workspace_id,
            "ip_id": ip.id,
            "ip_code": ip.code,
            "ip_name": ip.name,
            "series_id": series.id,
            "series_name": series.name,
            "series_summary": series.summary,
            "episode_id": episode.id,
            "episode_number": episode.number,
            "episode_title": episode.title,
            "episode_status": episode.status,
            "episode_default_style_version_id": episode.default_style_version_id,
            "revision_no": revision_no,
        },
        "brand": {
            "template_id": brand.id,
            "template_name": brand.name,
            "version_id": brand_version.id,
            "version_no": brand_version.version_no,
            "approved_at": brand_version.approved_at,
            "template_json": brand_json,
        },
        "styles": styles,
        "assets": manifest_assets,
    })

    manifest_bytes = json.dumps(
        manifest.model_dump(mode="json"), ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    document_bytes = json.dumps(
        document, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    if len(manifest_bytes) > MAX_MANIFEST_BYTES or len(document_bytes) > MAX_MANIFEST_BYTES:
        raise ProjectBundleConflict("Project manifest or document exceeds the portable size limit")
    if (
        sum(map(len, blob_files.values())) + len(manifest_bytes) + len(document_bytes)
        > MAX_BUNDLE_UNCOMPRESSED_BYTES
    ):
        raise ProjectBundleConflict("Project bundle exceeds the uncompressed size limit")

    output = BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED, allowZip64=False) as archive:
        archive.writestr("manifest.json", manifest_bytes)
        archive.writestr("document.json", document_bytes)
        for path, data in sorted(blob_files.items()):
            archive.writestr(path, data)
    bundle = output.getvalue()
    if len(bundle) > MAX_BUNDLE_UPLOAD_BYTES:
        raise ProjectBundleConflict("Project bundle exceeds the compressed file limit")
    return bundle


def _validate_zip_member(info: zipfile.ZipInfo) -> None:
    name = info.filename
    mode = (info.external_attr >> 16) & 0xFFFF
    kind = stat.S_IFMT(mode)
    if (
        not name
        or "\\" in name
        or "\x00" in name
        or PurePosixPath(name).is_absolute()
        or PureWindowsPath(name).drive
        or any(part in {"", ".", ".."} for part in name.split("/"))
        or info.is_dir()
        or (kind not in {0, stat.S_IFREG})
        or info.flag_bits & 1
        or info.compress_type not in {
            zipfile.ZIP_STORED,
            zipfile.ZIP_DEFLATED,
            zipfile.ZIP_BZIP2,
            zipfile.ZIP_LZMA,
        }
    ):
        raise ProjectBundleValidationError("ZIP contains an unsafe path, link, encrypted entry, or compression method")


def _required_bundle_asset_ids(
    document: CanvasDocument, manifest: ProjectManifest
) -> set[UUID]:
    document_json = document.model_dump(mode="json")
    brand_json = manifest.brand.template_json.model_dump(mode="json")
    style_snapshots = [style.model_dump(mode="json") for style in manifest.styles]
    return _required_asset_version_ids(document_json, brand_json, style_snapshots)


def _read_archive(
    payload: bytes,
    temporary_dir: Path,
    max_asset_bytes: int,
    max_pixels: int,
) -> tuple[ProjectManifest, CanvasDocument, dict[UUID, Path]]:
    if not payload or len(payload) > MAX_BUNDLE_UPLOAD_BYTES:
        raise ProjectBundleValidationError("Project bundle is empty or exceeds the upload limit", 413)
    try:
        archive = zipfile.ZipFile(BytesIO(payload), "r")
    except (zipfile.BadZipFile, OSError) as error:
        raise ProjectBundleValidationError("Uploaded file is not a valid project ZIP") from error
    with archive:
        infos = archive.infolist()
        if not 2 <= len(infos) <= MAX_BUNDLE_FILES:
            raise ProjectBundleValidationError("Project ZIP contains an invalid number of files")
        names: set[str] = set()
        total_size = 0
        for info in infos:
            _validate_zip_member(info)
            if info.filename in names:
                raise ProjectBundleValidationError("ZIP contains duplicate paths")
            names.add(info.filename)
            if info.file_size < 0 or info.file_size > max_asset_bytes and info.filename.startswith("blobs/"):
                raise ProjectBundleValidationError("A bundled asset exceeds the per-file size limit", 413)
            total_size += info.file_size
            if total_size > MAX_BUNDLE_UNCOMPRESSED_BYTES:
                raise ProjectBundleValidationError("Project ZIP exceeds the uncompressed size limit", 413)
        if "manifest.json" not in names or "document.json" not in names:
            raise ProjectBundleValidationError("Project ZIP is missing manifest.json or document.json")
        manifest_info = archive.getinfo("manifest.json")
        document_info = archive.getinfo("document.json")
        if manifest_info.file_size > MAX_MANIFEST_BYTES or document_info.file_size > MAX_MANIFEST_BYTES:
            raise ProjectBundleValidationError("Project manifest or document exceeds the size limit", 413)
        try:
            manifest = ProjectManifest.model_validate_json(archive.read(manifest_info))
            document = CanvasDocument.model_validate_json(archive.read(document_info))
        except (
            ValidationError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            OSError,
            RuntimeError,
            NotImplementedError,
            zipfile.BadZipFile,
        ) as error:
            raise ProjectBundleValidationError("Project manifest or document schema is invalid") from error

        if (
            document.episode_id != manifest.source.episode_id
            or document.revision != manifest.source.revision_no
            or document.brand_template_version_id != manifest.brand.version_id
        ):
            raise ProjectBundleValidationError("Manifest and document version references do not match")
        style_version_ids = {style.version_id for style in manifest.styles}
        if document.style_version_id is not None and document.style_version_id not in style_version_ids:
            raise ProjectBundleValidationError("Manifest is missing the document style version")
        if (
            manifest.source.episode_default_style_version_id is not None
            and manifest.source.episode_default_style_version_id not in style_version_ids
        ):
            raise ProjectBundleValidationError("Manifest is missing the episode default style version")
        required_asset_ids = _required_bundle_asset_ids(document, manifest)
        manifest_asset_ids = {asset.asset_version_id for asset in manifest.assets}
        if required_asset_ids != manifest_asset_ids:
            raise ProjectBundleValidationError("Bundle assets do not exactly match the project references")
        expected_names = {"manifest.json", "document.json"} | {asset.blob_path for asset in manifest.assets}
        if names != expected_names:
            raise ProjectBundleValidationError("ZIP paths do not match the manifest")

        extracted: dict[UUID, Path] = {}
        for asset in manifest.assets:
            info = archive.getinfo(asset.blob_path)
            if info.file_size != asset.byte_size or info.file_size > max_asset_bytes:
                raise ProjectBundleValidationError("Blob size does not match its manifest", 413)
            target_path = temporary_dir / f"{asset.sha256}.{MIME_EXTENSION[asset.mime]}"
            digest = hashlib.sha256()
            actual_size = 0
            try:
                with archive.open(info, "r") as source, target_path.open("wb") as target:
                    while chunk := source.read(64 * 1024):
                        actual_size += len(chunk)
                        if actual_size > max_asset_bytes:
                            raise ProjectBundleValidationError("A bundled asset exceeds the per-file size limit", 413)
                        digest.update(chunk)
                        target.write(chunk)
            except (OSError, RuntimeError, NotImplementedError, zipfile.BadZipFile) as error:
                raise ProjectBundleValidationError("A bundled Blob could not be read") from error
            if actual_size != asset.byte_size or digest.hexdigest() != asset.sha256:
                raise ProjectBundleValidationError("A bundled Blob is missing or failed its SHA-256 check")
            try:
                image = inspect_image(target_path.read_bytes(), asset.mime, max_asset_bytes, max_pixels)
            except AssetValidationError as error:
                raise ProjectBundleValidationError("A bundled Blob is not a valid supported image") from error
            if (image.width, image.height, image.alpha) != (asset.width, asset.height, asset.alpha):
                raise ProjectBundleValidationError("Blob image dimensions do not match the manifest")
            extracted[asset.asset_version_id] = target_path
        return manifest, document, extracted


def _asset_snapshot_matches(asset: Asset, snapshot: ProjectAssetSnapshot, ip_id: UUID) -> bool:
    return (
        asset.owner_ip_id == ip_id
        and asset.name == snapshot.name
        and asset.type == snapshot.type
        and asset.source_type == snapshot.source_type
        and asset.rights_note == snapshot.rights_note
    )


def _version_snapshot_matches(
    session: Session, version: AssetVersion, snapshot: ProjectAssetSnapshot, blob_sha256: str
) -> bool:
    blob = session.get(Blob, version.blob_id)
    return (
        version.version_no == snapshot.version_no
        and version.status == "approved"
        and (version.width, version.height, version.alpha) == (snapshot.width, snapshot.height, snapshot.alpha)
        and version.metadata_json == snapshot.metadata_json
        and blob is not None
        and blob.sha256 == blob_sha256
    )


def _can_reuse_asset(
    session: Session,
    workspace_id: UUID,
    ip_id: UUID,
    asset_id: UUID,
    snapshots: list[ProjectAssetSnapshot],
) -> tuple[Asset | None, dict[UUID, UUID]]:
    asset = session.get(Asset, asset_id)
    if asset is None or asset.workspace_id != workspace_id or not _asset_snapshot_matches(asset, snapshots[0], ip_id):
        return None, {}
    version_map: dict[UUID, UUID] = {}
    for snapshot in snapshots:
        version = session.get(AssetVersion, snapshot.asset_version_id)
        if version is not None:
            if version.asset_id != asset.id or not _version_snapshot_matches(
                session, version, snapshot, snapshot.sha256
            ):
                return None, {}
            version_map[snapshot.asset_version_id] = version.id
            continue
        same_number = session.scalar(
            select(AssetVersion).where(
                AssetVersion.asset_id == asset.id,
                AssetVersion.version_no == snapshot.version_no,
            )
        )
        if same_number is not None:
            if not _version_snapshot_matches(session, same_number, snapshot, snapshot.sha256):
                return None, {}
            version_map[snapshot.asset_version_id] = same_number.id
    return asset, version_map


def _put_verified_blob(
    session: Session,
    asset: ProjectAssetSnapshot,
    source_path: Path,
    storage_dir: Path,
    created_blob_paths: list[tuple[str, Path]],
) -> Blob:
    blob = session.scalar(select(Blob).where(Blob.sha256 == asset.sha256))
    if blob is not None:
        if blob.mime != asset.mime or blob.byte_size != asset.byte_size:
            raise ProjectBundleConflict("Stored Blob metadata conflicts with the project manifest")
        target = resolve_blob_path(storage_dir, blob.storage_key)
        if not target.is_file() or _hash_file(target) != asset.sha256:
            put_blob(source_path.read_bytes(), asset.sha256, storage_dir)
        return blob

    target_key = f"{asset.sha256[:2]}/{asset.sha256}"
    target = resolve_blob_path(storage_dir, target_key)
    existed = target.is_file()
    data = source_path.read_bytes()
    storage_key = put_blob(data, asset.sha256, storage_dir)
    if not existed:
        created_blob_paths.append((asset.sha256, target))
    blob = Blob(
        id=uuid4(), sha256=asset.sha256, storage_key=storage_key,
        mime=asset.mime, byte_size=asset.byte_size,
    )
    session.add(blob)
    session.flush()
    return blob


def _remap_style_bible(bible: dict[str, Any], asset_map: dict[UUID, UUID]) -> dict[str, Any]:
    result = deepcopy(bible)
    references = result.get("example_asset_version_ids", [])
    result["example_asset_version_ids"] = [str(asset_map[UUID(str(item))]) for item in references]
    return result


def _persist_bundle(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    target_ip_id: UUID,
    manifest: ProjectManifest,
    source_document: CanvasDocument,
    extracted_blobs: dict[UUID, Path],
    storage_dir: Path,
) -> dict[str, Any]:
    target_ip = session.scalar(select(IP).where(IP.id == target_ip_id, IP.workspace_id == workspace_id))
    if target_ip is None:
        raise ProjectBundleNotFound("Target IP not found")

    created_blob_paths: list[tuple[str, Path]] = []
    try:
        blob_by_version: dict[UUID, Blob] = {}
        for snapshot in manifest.assets:
            blob_by_version[snapshot.asset_version_id] = _put_verified_blob(
                session, snapshot, extracted_blobs[snapshot.asset_version_id], storage_dir, created_blob_paths
            )

        by_asset: dict[UUID, list[ProjectAssetSnapshot]] = {}
        for snapshot in manifest.assets:
            by_asset.setdefault(snapshot.asset_id, []).append(snapshot)
        asset_version_id_map: dict[UUID, UUID] = {}
        now = datetime.now(timezone.utc)
        for source_asset_id, snapshots in by_asset.items():
            snapshots.sort(key=lambda value: value.version_no)
            asset, reusable_versions = _can_reuse_asset(
                session, workspace_id, target_ip_id, source_asset_id, snapshots
            )
            if asset is None:
                asset_id = source_asset_id if session.get(Asset, source_asset_id) is None else uuid4()
                first = snapshots[0]
                asset = Asset(
                    id=asset_id,
                    workspace_id=workspace_id,
                    owner_ip_id=target_ip_id,
                    type=first.type,
                    name=first.name,
                    status="approved",
                    source_type=first.source_type,
                    rights_note=first.rights_note,
                )
                session.add(asset)
                session.flush()
                reusable_versions = {}
            for snapshot in snapshots:
                if snapshot.asset_version_id in reusable_versions:
                    asset_version_id_map[snapshot.asset_version_id] = reusable_versions[snapshot.asset_version_id]
                    continue
                source_id = snapshot.asset_version_id
                new_version_id = source_id if session.get(AssetVersion, source_id) is None else uuid4()
                version = AssetVersion(
                    id=new_version_id,
                    workspace_id=workspace_id,
                    asset_id=asset.id,
                    version_no=snapshot.version_no,
                    blob_id=blob_by_version[source_id].id,
                    width=snapshot.width,
                    height=snapshot.height,
                    alpha=snapshot.alpha,
                    metadata_json=snapshot.metadata_json,
                    status="approved",
                    approved_at=now,
                    approved_by_user_id=user_id,
                )
                session.add(version)
                session.flush()
                asset_version_id_map[source_id] = version.id

        brand_json = manifest.brand.template_json.model_dump(mode="json")
        for element in brand_json["locked_elements"]:
            old_id = element.get("asset_version_id")
            if old_id:
                element["asset_version_id"] = str(asset_version_id_map[UUID(str(old_id))])

        source_brand_version = session.get(BrandTemplateVersion, manifest.brand.version_id)
        if source_brand_version is not None:
            source_brand_template = session.get(BrandTemplate, source_brand_version.brand_template_id)
        else:
            source_brand_template = None
        if (
            source_brand_version is not None
            and source_brand_template is not None
            and source_brand_template.workspace_id == workspace_id
            and source_brand_template.ip_id == target_ip_id
            and source_brand_template.name == manifest.brand.template_name
            and source_brand_version.status == "approved"
            and source_brand_version.template_json == brand_json
        ):
            brand_template = source_brand_template
            brand_version = source_brand_version
        else:
            brand_template_id = (
                manifest.brand.template_id
                if session.get(BrandTemplate, manifest.brand.template_id) is None
                else uuid4()
            )
            brand_template = BrandTemplate(
                id=brand_template_id,
                workspace_id=workspace_id,
                ip_id=target_ip_id,
                name=manifest.brand.template_name,
            )
            session.add(brand_template)
            session.flush()
            version_id = (
                manifest.brand.version_id
                if session.get(BrandTemplateVersion, manifest.brand.version_id) is None
                else uuid4()
            )
            brand_version = BrandTemplateVersion(
                id=version_id,
                workspace_id=workspace_id,
                brand_template_id=brand_template.id,
                version_no=manifest.brand.version_no,
                template_json=brand_json,
                status="approved",
                approved_at=now,
                approved_by_user_id=user_id,
            )
            session.add(brand_version)
            session.flush()

        style_version_map: dict[UUID, UUID] = {}
        imported_styles: dict[UUID, StyleVersion] = {}
        for snapshot in manifest.styles:
            bible = _remap_style_bible(snapshot.bible_json, asset_version_id_map)
            source_version = session.get(StyleVersion, snapshot.version_id)
            source_style = session.get(Style, source_version.style_id) if source_version else None
            if (
                source_version is not None
                and source_style is not None
                and source_style.workspace_id == workspace_id
                and source_style.ip_id == target_ip_id
                and source_style.name == snapshot.style_name
                and source_version.status == "approved"
                and source_version.bible_json == bible
            ):
                imported_style = source_style
                imported_version = source_version
            else:
                style_id = snapshot.style_id if session.get(Style, snapshot.style_id) is None else uuid4()
                imported_style = Style(
                    id=style_id,
                    workspace_id=workspace_id,
                    ip_id=target_ip_id,
                    name=snapshot.style_name,
                )
                session.add(imported_style)
                session.flush()
                style_version_id = snapshot.version_id if session.get(StyleVersion, snapshot.version_id) is None else uuid4()
                imported_version = StyleVersion(
                    id=style_version_id,
                    workspace_id=workspace_id,
                    style_id=imported_style.id,
                    version_no=snapshot.version_no,
                    bible_json=bible,
                    status="approved",
                    approved_at=now,
                    approved_by_user_id=user_id,
                )
                session.add(imported_version)
                session.flush()
            style_version_map[snapshot.version_id] = imported_version.id
            imported_styles[snapshot.version_id] = imported_version

        series = Series(
            workspace_id=workspace_id,
            ip_id=target_ip_id,
            name=manifest.source.series_name,
            summary=manifest.source.series_summary,
        )
        session.add(series)
        session.flush()
        episode_default_style_id = manifest.source.episode_default_style_version_id
        episode = Episode(
            workspace_id=workspace_id,
            series_id=series.id,
            number=manifest.source.episode_number,
            title=manifest.source.episode_title,
            status=manifest.source.episode_status,
            default_style_version_id=style_version_map.get(episode_default_style_id)
            if episode_default_style_id is not None else None,
        )
        session.add(episode)
        session.flush()

        imported_document = source_document.model_dump(mode="json")
        imported_document["episode_id"] = str(episode.id)
        imported_document["revision"] = 1
        imported_document["brand_template_version_id"] = str(brand_version.id)
        imported_document["style_version_id"] = (
            str(style_version_map[source_document.style_version_id])
            if source_document.style_version_id is not None else None
        )
        for page in imported_document["pages"]:
            page["brand_template_version_id"] = str(brand_version.id)
            for panel in page["panels"]:
                for element in panel["elements"]:
                    if element.get("type") in {"image", "sticker"}:
                        element["asset_version_id"] = str(
                            asset_version_id_map[UUID(str(element["asset_version_id"]))]
                        )

        for page in imported_document["pages"]:
            for panel in page["panels"]:
                for element in panel["elements"]:
                    if element.get("type") in {"image", "sticker"}:
                        session.add(AssetLink(
                            asset_version_id=UUID(element["asset_version_id"]),
                            owner_type="canvas_element",
                            owner_id=element["id"],
                            role=element["type"],
                        ))
        for element in brand_json["locked_elements"]:
            if element.get("asset_version_id"):
                session.add(AssetLink(
                    asset_version_id=UUID(str(element["asset_version_id"])),
                    owner_type="brand_template_version",
                    owner_id=str(brand_version.id),
                    role=element["kind"],
                ))
        for version in imported_styles.values():
            for asset_version_id in version.bible_json.get("example_asset_version_ids", []):
                session.add(AssetLink(
                    asset_version_id=UUID(str(asset_version_id)),
                    owner_type="style_version",
                    owner_id=str(version.id),
                    role="example",
                ))

        try:
            revision_no, _saved_document = save_document(
                session,
                workspace_id,
                episode.id,
                0,
                imported_document,
                note=f"Imported project bundle from revision {manifest.source.revision_no}",
                commit=False,
            )
            session.commit()
        except (DocumentConflict, DocumentNotFound, IntegrityError) as error:
            session.rollback()
            _cleanup_created_blobs(session, created_blob_paths)
            raise ProjectBundleConflict("Project import could not be committed") from error
        return {
            "ip_id": target_ip_id,
            "series_id": series.id,
            "episode_id": episode.id,
            "revision_no": revision_no,
            "brand_template_version_id": brand_version.id,
            "style_version_id": imported_document["style_version_id"],
            "asset_version_id_map": asset_version_id_map,
        }
    except BaseException:
        if session.is_active:
            session.rollback()
        _cleanup_created_blobs(session, created_blob_paths)
        raise


def _cleanup_created_blobs(session: Session, created_paths: list[tuple[str, Path]]) -> None:
    for sha256, path in created_paths:
        referenced = session.scalar(select(Blob.id).where(Blob.sha256 == sha256))
        if referenced is None:
            path.unlink(missing_ok=True)


def import_project_bundle(
    session: Session,
    workspace_id: UUID,
    user_id: UUID,
    target_ip_id: UUID,
    payload: bytes,
    storage_dir: Path,
    max_asset_bytes: int,
    max_pixels: int,
) -> dict[str, Any]:
    try:
        with tempfile.TemporaryDirectory(prefix="ip-studio-project-import-") as raw_dir:
            temporary_dir = Path(raw_dir).resolve()
            manifest, document, extracted_blobs = _read_archive(
                payload, temporary_dir, max_asset_bytes, max_pixels
            )
            session.rollback()
            return _persist_bundle(
                session,
                workspace_id,
                user_id,
                target_ip_id,
                manifest,
                document,
                extracted_blobs,
                storage_dir,
            )
    except ProjectBundleValidationError:
        raise
    except (zipfile.BadZipFile, OSError, ValueError, ValidationError) as error:
        raise ProjectBundleValidationError("Project bundle could not be validated") from error
