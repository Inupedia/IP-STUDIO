from collections.abc import Iterator
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import func, select

from app.main import create_app
from app.models.assets import Asset, AssetLink, AssetVersion, Blob

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
MAX_IMAGE_BYTES = 25 * 1024 * 1024


def image_bytes(image_format: str = "PNG", size: tuple[int, int] = (2, 2)) -> bytes:
    output = BytesIO()
    mode = "RGB" if image_format == "JPEG" else "RGBA"
    Image.new(mode, size, (24, 100, 180, 200)).save(output, format=image_format)
    return output.getvalue()


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


def create_ip(client: TestClient, code: str = "LAG") -> str:
    response = client.post("/api/v1/ips", json={"code": code, "name": f"IP {code}"})
    assert response.status_code == 201
    return response.json()["id"]


def upload(client: TestClient, ip_id: str, content: bytes, mime: str = "image/png", name: str = "source.png"):
    return client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": name, "type": "character_reference"},
        files={"file": (name, content, mime)},
    )


def test_three_ips_keep_their_uploaded_assets_separate(client: TestClient) -> None:
    ip_ids = [create_ip(client, code) for code in ("KAZI", "PULU", "LING")]
    uploaded = [
        upload(client, ip_id, image_bytes(size=(index + 2, 2)), name=f"ip-{index}.png")
        for index, ip_id in enumerate(ip_ids)
    ]

    assert all(response.status_code == 201 for response in uploaded)
    for index, ip_id in enumerate(ip_ids):
        assets = client.get("/api/v1/assets", params={"ip_id": ip_id})
        assert assets.status_code == 200
        assert len(assets.json()) == 1
        assert assets.json()[0]["owner_ip_id"] == ip_id
        assert assets.json()[0]["name"] == f"ip-{index}.png"


def test_reject_fake_png(client: TestClient) -> None:
    response = upload(client, create_ip(client), b"<html>not a png</html>")

    assert response.status_code == 415
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 0
        assert session.scalar(select(func.count()).select_from(Blob)) == 0


def test_reject_upload_over_25mb(client: TestClient) -> None:
    response = upload(client, create_ip(client), b"x" * (MAX_IMAGE_BYTES + 1))

    assert response.status_code == 413


def test_reject_mime_content_mismatch(client: TestClient) -> None:
    response = upload(client, create_ip(client), image_bytes(), mime="image/jpeg")

    assert response.status_code == 415


@pytest.mark.parametrize(
    ("image_format", "mime"),
    [("JPEG", "image/jpeg"), ("WEBP", "image/webp")],
)
def test_supported_raster_formats_are_decoded(
    client: TestClient, image_format: str, mime: str
) -> None:
    response = upload(client, create_ip(client), image_bytes(image_format), mime=mime)

    assert response.status_code == 201
    assert response.json()["mime"] == mime


def test_reject_image_over_pixel_limit(client: TestClient) -> None:
    client.app.state.asset_max_pixels = 3
    response = upload(client, create_ip(client), image_bytes())

    assert response.status_code == 413


def test_sha256_dedupe(client: TestClient) -> None:
    ip_id = create_ip(client)
    content = image_bytes()
    first = upload(client, ip_id, content, name="first.png")
    second = upload(client, ip_id, content, name="renamed.png")

    assert first.status_code == second.status_code == 201
    assert first.json()["sha256"] == second.json()["sha256"]
    assert first.json()["asset_version_id"] != second.json()["asset_version_id"]
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Blob)) == 1
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 2
    stored_files = [path for path in client.app.state.asset_storage_dir.rglob("*") if path.is_file()]
    assert len(stored_files) == 1


def test_cross_ip_denied(client: TestClient) -> None:
    owner_ip_id = create_ip(client, "OWNER")
    other_ip_id = create_ip(client, "OTHER")
    uploaded = upload(client, owner_ip_id, image_bytes())
    assert uploaded.status_code == 201

    response = client.get(
        f"/api/v1/assets/{uploaded.json()['asset_id']}", params={"ip_id": other_ip_id}
    )

    assert response.status_code == 404


def test_asset_content_is_served_only_in_its_ip_scope(client: TestClient) -> None:
    owner_ip_id = create_ip(client, "OWNER")
    other_ip_id = create_ip(client, "OTHER")
    content = image_bytes()
    uploaded = upload(client, owner_ip_id, content)
    assert uploaded.status_code == 201
    asset_id = uploaded.json()["asset_id"]

    allowed = client.get(f"/api/v1/assets/{asset_id}/content", params={"ip_id": owner_ip_id})
    denied = client.get(f"/api/v1/assets/{asset_id}/content", params={"ip_id": other_ip_id})

    assert allowed.status_code == 200
    assert allowed.content == content
    assert denied.status_code == 404


def test_delete_used_asset_blocked(client: TestClient) -> None:
    ip_id = create_ip(client)
    response = upload(client, ip_id, image_bytes())
    assert response.status_code == 201
    uploaded = response.json()
    with client.app.state.session_factory.begin() as session:
        session.add(
            AssetLink(
                asset_version_id=UUID(uploaded["asset_version_id"]),
                owner_type="canvas_element",
                owner_id="canvas-element-1",
                role="image",
            )
        )
        blob = session.scalar(select(Blob).where(Blob.sha256 == uploaded["sha256"]))
        assert blob is not None
        storage_path = client.app.state.asset_storage_dir / blob.storage_key

    deleted = client.delete(
        f"/api/v1/assets/{uploaded['asset_id']}", params={"ip_id": ip_id, "confirm": "true"}
    )

    assert deleted.status_code == 409
    assert storage_path.is_file()
    with client.app.state.session_factory() as session:
        assert session.get(Asset, UUID(uploaded["asset_id"])) is not None


def test_delete_requires_explicit_confirmation(client: TestClient) -> None:
    ip_id = create_ip(client)
    response = upload(client, ip_id, image_bytes())
    assert response.status_code == 201

    deleted = client.delete(
        f"/api/v1/assets/{response.json()['asset_id']}", params={"ip_id": ip_id}
    )

    assert deleted.status_code == 400
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Asset)) == 1


def test_delete_unused_asset_preserves_shared_blob_until_last_version(client: TestClient) -> None:
    ip_id = create_ip(client)
    content = image_bytes()
    first = upload(client, ip_id, content, name="first.png")
    second = upload(client, ip_id, content, name="second.png")
    assert first.status_code == second.status_code == 201

    first_delete = client.delete(
        f"/api/v1/assets/{first.json()['asset_id']}",
        params={"ip_id": ip_id, "confirm": "true"},
    )
    assert first_delete.status_code == 204
    assert len([path for path in client.app.state.asset_storage_dir.rglob("*") if path.is_file()]) == 1
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(Blob)) == 1

    second_delete = client.delete(
        f"/api/v1/assets/{second.json()['asset_id']}",
        params={"ip_id": ip_id, "confirm": "true"},
    )

    assert second_delete.status_code == 204
    assert not [path for path in client.app.state.asset_storage_dir.rglob("*") if path.is_file()]


def test_new_asset_version_keeps_previous_version_immutable(client: TestClient) -> None:
    ip_id = create_ip(client)
    first_content = image_bytes("PNG")
    first = upload(client, ip_id, first_content)
    assert first.status_code == 201
    asset_id = first.json()["asset_id"]
    second_content = image_bytes("WEBP")

    second = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data={"ip_id": ip_id},
        files={"file": ("new.webp", second_content, "image/webp")},
    )

    assert second.status_code == 201
    assert second.json()["asset_id"] == asset_id
    assert second.json()["asset_version_id"] != first.json()["asset_version_id"]
    assert second.json()["version_no"] == 2
    assert second.json()["sha256"] != first.json()["sha256"]
    old_content = client.get(
        f"/api/v1/assets/{asset_id}/content",
        params={"ip_id": ip_id, "version_id": first.json()["asset_version_id"]},
    )
    latest_content = client.get(
        f"/api/v1/assets/{asset_id}/content", params={"ip_id": ip_id}
    )
    assert old_content.content == first_content
    assert latest_content.content == second_content
    with client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AssetVersion)) == 2


def test_frozen_asset_version_can_be_resolved_after_new_version_upload(client: TestClient) -> None:
    ip_id = create_ip(client, "FROZEN")
    other_ip_id = create_ip(client, "OTHER")
    first = upload(client, ip_id, image_bytes("PNG"))
    assert first.status_code == 201
    asset_id = first.json()["asset_id"]
    old_version_id = first.json()["asset_version_id"]
    second = client.post(
        f"/api/v1/assets/{asset_id}/versions",
        data={"ip_id": ip_id},
        files={"file": ("new.webp", image_bytes("WEBP"), "image/webp")},
    )
    assert second.status_code == 201

    resolved = client.get(
        f"/api/v1/assets/versions/{old_version_id}",
        params={"ip_id": ip_id},
    )
    denied = client.get(
        f"/api/v1/assets/versions/{old_version_id}",
        params={"ip_id": other_ip_id},
    )

    assert resolved.status_code == 200
    assert resolved.json()["asset_id"] == asset_id
    assert resolved.json()["asset_version_id"] == old_version_id
    assert resolved.json()["version_no"] == 1
    assert denied.status_code == 404
