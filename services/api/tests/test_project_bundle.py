from collections.abc import Iterator
from io import BytesIO
import json
from pathlib import Path
import stat
from uuid import UUID, uuid4
from zipfile import ZIP_STORED, ZipFile, ZipInfo

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app
from app.models.assets import AssetVersion
from sqlalchemy import select

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'ip-studio-test.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
    )
    with TestClient(application) as test_client:
        token_response = test_client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert token_response.status_code == 200
        test_client.headers["Authorization"] = f"Bearer {token_response.json()['access_token']}"
        yield test_client


def create_project(client: TestClient) -> tuple[str, str, str, str, str, bytes]:
    ip = client.post("/api/v1/ips", json={"code": "LAG", "name": "卡仔"})
    assert ip.status_code == 201, ip.text
    series = client.post(
        "/api/v1/series", json={"ip_id": ip.json()["id"], "name": "人间卡顿局"}
    )
    assert series.status_code == 201, series.text
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "在吗？"},
    )
    assert episode.status_code == 201, episode.text
    template = client.post(
        f"/api/v1/ips/{ip.json()['id']}/brand-templates",
        json={
            "name": "固定外壳",
            "template": {
                "schema_version": "1.0",
                "width": 1080,
                "height": 1440,
                "locked_elements": [
                    {"id": "logo-main", "kind": "logo", "locked": True,
                     "x": 48, "y": 40, "width": 120, "height": 60, "fill": "#243a2d"},
                    {"id": "footer-main", "kind": "footer", "locked": True,
                     "x": 48, "y": 1380, "width": 984, "height": 24, "fill": "#eeeeee"},
                ],
                "dynamic_slots": {
                    "title": {"x": 160, "y": 40, "width": 760, "height": 100},
                    "episode_number": {"x": 900, "y": 48, "width": 120, "height": 52},
                },
            },
        },
    )
    assert template.status_code == 201, template.text
    brand_version_id = template.json()["brand_template_version_id"]
    approved_brand = client.post(f"/api/v1/brand-template-versions/{brand_version_id}/approve")
    assert approved_brand.status_code == 200, approved_brand.text

    output = BytesIO()
    Image.new("RGBA", (8, 8), (40, 120, 180, 200)).save(output, format="PNG")
    uploaded = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip.json()["id"], "name": "卡仔单格", "type": "composite_panel"},
        files={"file": ("panel.png", output.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    asset_version_id = uploaded.json()["asset_version_id"]
    approved_asset = client.post(
        f"/api/v1/assets/{uploaded.json()['asset_id']}/versions/{asset_version_id}/approve",
        params={"ip_id": ip.json()["id"]},
    )
    assert approved_asset.status_code == 200, approved_asset.text

    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["episode_id"] = episode.json()["id"]
    document["brand_template_version_id"] = brand_version_id
    document["style_version_id"] = None
    document["dynamic_fields"] = {"title": "在吗？", "episode_number": "EP.01"}
    for page in document["pages"]:
        page["brand_template_version_id"] = brand_version_id
        for panel in page["panels"]:
            for element in panel["elements"]:
                if element["type"] == "image":
                    element["asset_version_id"] = asset_version_id
    saved = client.put(
        f"/api/v1/episodes/{episode.json()['id']}/document",
        json={"base_revision": 0, "document": document},
    )
    assert saved.status_code == 200, saved.text
    bundle_response = client.post(
        f"/api/v1/episodes/{episode.json()['id']}/project-bundle",
        json={"revision_no": 1},
    )
    assert bundle_response.status_code == 200, bundle_response.text
    assert bundle_response.headers["content-type"].startswith("application/zip")
    assert "attachment; filename=" in bundle_response.headers["content-disposition"]
    return (
        ip.json()["id"], episode.json()["id"], brand_version_id,
        uploaded.json()["asset_id"], asset_version_id, bundle_response.content,
    )


def import_bundle(client: TestClient, ip_id: str, bundle: bytes):
    return client.post(
        "/api/v1/projects/import",
        data={"ip_id": ip_id},
        files={"file": ("project.zip", bundle, "application/zip")},
    )


def add_zip_member(bundle: bytes, info: str | ZipInfo, content: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(bundle), "r") as source, ZipFile(output, "w", compression=ZIP_STORED) as target:
        for item in source.infolist():
            target.writestr(item, source.read(item.filename))
        target.writestr(info, content)
    return output.getvalue()


def replace_zip_member(bundle: bytes, member_name: str, content: bytes) -> bytes:
    output = BytesIO()
    with ZipFile(BytesIO(bundle), "r") as source, ZipFile(output, "w", compression=ZIP_STORED) as target:
        for item in source.infolist():
            target.writestr(item, content if item.filename == member_name else source.read(item.filename))
    return output.getvalue()


def test_zip_roundtrip_preserves_layers_assets_and_brand_version(client: TestClient) -> None:
    ip_id, source_episode_id, brand_version_id, asset_id, asset_version_id, bundle = create_project(client)

    imported = import_bundle(client, ip_id, bundle)

    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert result["episode_id"] != source_episode_id
    assert result["brand_template_version_id"] == brand_version_id
    assert result["asset_version_id_map"][asset_version_id] == asset_version_id
    document = client.get(f"/api/v1/episodes/{result['episode_id']}/document")
    assert document.status_code == 200
    imported_document = document.json()["document"]
    assert imported_document["revision"] == 1
    assert imported_document["dynamic_fields"]["title"] == "在吗？"
    assert imported_document["brand_template_version_id"] == brand_version_id
    image = next(
        element
        for page in imported_document["pages"]
        for panel in page["panels"]
        for element in panel["elements"]
        if element["type"] == "image"
    )
    assert image["asset_version_id"] == asset_version_id
    with client.app.state.session_factory() as session:
        version = session.scalar(select(AssetVersion).where(AssetVersion.id == UUID(asset_version_id)))
        assert version is not None and str(version.asset_id) == asset_id


def test_missing_blob_is_rejected_without_import_side_effects(client: TestClient) -> None:
    ip_id, _, _, _, _, bundle = create_project(client)
    with ZipFile(BytesIO(bundle)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        omitted_path = manifest["assets"][0]["blob_path"]
        incomplete = BytesIO()
        with ZipFile(incomplete, "w", compression=ZIP_STORED) as rebuilt:
            for item in archive.infolist():
                if item.filename != omitted_path:
                    rebuilt.writestr(item, archive.read(item.filename))
    episode_count_before = len(client.get("/api/v1/series", params={"ip_id": ip_id}).json())

    imported = import_bundle(client, ip_id, incomplete.getvalue())

    assert imported.status_code == 422
    assert len(client.get("/api/v1/series", params={"ip_id": ip_id}).json()) == episode_count_before


def test_blob_hash_mismatch_is_rejected_before_target_ip_changes(client: TestClient) -> None:
    _, _, _, _, _, bundle = create_project(client)
    target_ip = client.post("/api/v1/ips", json={"code": "SAFE", "name": "安全校验"})
    assert target_ip.status_code == 201
    with ZipFile(BytesIO(bundle), "r") as archive:
        manifest = json.loads(archive.read("manifest.json"))
    blob_path = manifest["assets"][0]["blob_path"]
    with ZipFile(BytesIO(bundle), "r") as archive:
        blob = archive.read(blob_path)
    corrupted = replace_zip_member(bundle, blob_path, blob[:-1] + bytes([blob[-1] ^ 1]))

    imported = import_bundle(client, target_ip.json()["id"], corrupted)

    assert imported.status_code == 422
    assert client.get("/api/v1/series", params={"ip_id": target_ip.json()["id"]}).json() == []
    assert client.get("/api/v1/assets", params={"ip_id": target_ip.json()["id"]}).json() == []


@pytest.mark.parametrize("unsafe_name", ["../escape.txt", "/absolute.txt", "C:/drive.txt"])
def test_zip_slip_paths_are_rejected(client: TestClient, unsafe_name: str) -> None:
    ip_id, _, _, _, _, bundle = create_project(client)
    malicious = add_zip_member(bundle, unsafe_name, b"escape")

    imported = import_bundle(client, ip_id, malicious)

    assert imported.status_code == 422


def test_zip_symlinks_are_rejected(client: TestClient) -> None:
    ip_id, _, _, _, _, bundle = create_project(client)
    info = ZipInfo("blobs/link.png")
    info.create_system = 3
    info.external_attr = (stat.S_IFLNK | 0o777) << 16

    imported = import_bundle(client, ip_id, add_zip_member(bundle, info, b"../outside.png"))

    assert imported.status_code == 422


def test_duplicate_zip_entries_are_rejected(client: TestClient) -> None:
    ip_id, _, _, _, _, bundle = create_project(client)
    with pytest.warns(UserWarning, match="Duplicate name"):
        malicious = add_zip_member(bundle, "manifest.json", b"{}")

    imported = import_bundle(client, ip_id, malicious)

    assert imported.status_code == 422


def test_unsupported_zip_compression_is_rejected(client: TestClient) -> None:
    ip_id, _, _, _, _, bundle = create_project(client)
    unsupported = bytearray(bundle)
    local_header = unsupported.find(b"PK\x03\x04")
    central_header = unsupported.find(b"PK\x01\x02")
    assert local_header >= 0 and central_header >= 0
    unsupported[local_header + 8:local_header + 10] = (99).to_bytes(2, "little")
    unsupported[central_header + 10:central_header + 12] = (99).to_bytes(2, "little")

    imported = import_bundle(client, ip_id, bytes(unsupported))

    assert imported.status_code == 422


def test_zip_bomb_uncompressed_size_limit_is_enforced(client: TestClient, monkeypatch) -> None:
    import app.export.project_bundle as project_bundle

    ip_id, _, _, _, _, bundle = create_project(client)
    monkeypatch.setattr(project_bundle, "MAX_BUNDLE_UNCOMPRESSED_BYTES", 1024)
    bomb = add_zip_member(bundle, "extra.dat", b"x" * 2048)

    imported = import_bundle(client, ip_id, bomb)

    assert imported.status_code == 413


def test_export_rejects_manifest_over_portable_limit(client: TestClient, monkeypatch) -> None:
    import app.export.project_bundle as project_bundle

    _, episode_id, _, _, _, _ = create_project(client)
    monkeypatch.setattr(project_bundle, "MAX_MANIFEST_BYTES", 1)

    exported = client.post(
        f"/api/v1/episodes/{episode_id}/project-bundle", json={"revision_no": 1}
    )

    assert exported.status_code == 409


def test_bundle_import_to_another_ip_remaps_asset_and_shell_versions(client: TestClient) -> None:
    _, _, source_brand_id, _, source_asset_version_id, bundle = create_project(client)
    target_ip = client.post("/api/v1/ips", json={"code": "OTHER", "name": "目标 IP"})
    assert target_ip.status_code == 201

    imported = import_bundle(client, target_ip.json()["id"], bundle)

    assert imported.status_code == 201, imported.text
    result = imported.json()
    assert result["asset_version_id_map"][source_asset_version_id] != source_asset_version_id
    assert result["brand_template_version_id"] != source_brand_id
    listed_assets = client.get("/api/v1/assets", params={"ip_id": target_ip.json()["id"]})
    assert listed_assets.status_code == 200
    assert any(
        asset["asset_version_id"] == result["asset_version_id_map"][source_asset_version_id]
        for asset in listed_assets.json()
    )
