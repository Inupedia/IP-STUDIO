from collections.abc import Iterator
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def brand_shell(logo_id: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "width": 1080,
        "height": 1440,
        "locked_elements": [
            {"id": logo_id, "kind": "logo", "locked": True, "x": 30, "y": 30, "width": 100, "height": 50}
        ],
        "dynamic_slots": {
            "title": {"x": 100, "y": 60, "width": 800, "height": 100},
            "episode_number": {"x": 900, "y": 40, "width": 120, "height": 50},
        },
    }


def build_document(episode_id: str, brand_version_id: str) -> dict[str, object]:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["episode_id"] = episode_id
    document["brand_template_version_id"] = brand_version_id
    document["style_version_id"] = None
    for page in document["pages"]:
        page["brand_template_version_id"] = brand_version_id
        page["panels"][0]["elements"] = [
            element for element in page["panels"][0]["elements"] if element["type"] != "image"
        ]
    return document


def create_episode(client: TestClient, code: str = "LAG") -> tuple[str, str]:
    ip = client.post("/api/v1/ips", json={"code": code, "name": f"IP {code}"})
    assert ip.status_code == 201
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "日常"})
    assert series.status_code == 201
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "在吗？"},
    )
    assert episode.status_code == 201
    return ip.json()["id"], episode.json()["id"]


def approve_brand(client: TestClient, ip_id: str) -> tuple[str, str]:
    response = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates",
        json={"name": "固定外壳", "template": brand_shell(f"logo-{uuid4()}")},
    )
    assert response.status_code == 201, response.text
    version_id = response.json()["brand_template_version_id"]
    approved = client.post(f"/api/v1/brand-template-versions/{version_id}/approve")
    assert approved.status_code == 200
    return response.json()["brand_template_id"], version_id


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


def test_document_conflict_returns_409_and_keeps_the_winning_revision(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    _, brand_version_id = approve_brand(client, ip_id)
    first_document = build_document(episode_id, brand_version_id)
    first_document["dynamic_fields"]["title"] = "服务器保存"
    first = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": first_document},
    )

    conflicting_document = build_document(episode_id, brand_version_id)
    conflicting_document["dynamic_fields"]["title"] = "另一个标签页的覆盖"
    conflict = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": conflicting_document},
    )
    current = client.get(f"/api/v1/episodes/{episode_id}/document")

    assert first.status_code == 200, first.text
    assert first.json()["revision"] == 1
    assert conflict.status_code == 409
    assert current.status_code == 200
    assert current.json()["document"]["dynamic_fields"]["title"] == "服务器保存"


def test_episode_document_cannot_silently_migrate_brand_version(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    template_id, first_brand_version_id = approve_brand(client, ip_id)
    initial = build_document(episode_id, first_brand_version_id)
    saved = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": initial},
    )
    assert saved.status_code == 200, saved.text

    derived = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates/{template_id}/versions",
        json={"base_version_id": first_brand_version_id, "template": brand_shell("logo-v2")},
    )
    assert derived.status_code == 201
    approved = client.post(
        f"/api/v1/brand-template-versions/{derived.json()['brand_template_version_id']}/approve"
    )
    assert approved.status_code == 200

    migrated = build_document(episode_id, derived.json()["brand_template_version_id"])
    response = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 1, "document": migrated},
    )
    current = client.get(f"/api/v1/episodes/{episode_id}/document")

    assert response.status_code == 409
    assert current.json()["document"]["brand_template_version_id"] == first_brand_version_id


def test_restore_creates_a_new_revision_without_erasing_history(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    _, brand_version_id = approve_brand(client, ip_id)
    first_document = build_document(episode_id, brand_version_id)
    first_document["dynamic_fields"]["title"] = "初始标题"
    first = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": first_document},
    )
    second_document = build_document(episode_id, brand_version_id)
    second_document["dynamic_fields"]["title"] = "修改后的标题"
    second = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 1, "document": second_document},
    )

    restored = client.post(
        f"/api/v1/episodes/{episode_id}/restore/1",
        json={"base_revision": 2},
    )
    revisions = client.get(f"/api/v1/episodes/{episode_id}/revisions")
    current = client.get(f"/api/v1/episodes/{episode_id}/document")

    assert first.status_code == second.status_code == 200
    assert restored.status_code == 200, restored.text
    assert restored.json()["revision"] == 3
    assert current.json()["document"]["dynamic_fields"]["title"] == "初始标题"
    assert [revision["revision_no"] for revision in revisions.json()] == [3, 2, 1]


def test_document_rejects_asset_version_owned_by_another_ip(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    other_ip = client.post("/api/v1/ips", json={"code": "PENG", "name": "噗噜"})
    assert other_ip.status_code == 201
    _, brand_version_id = approve_brand(client, ip_id)
    output = BytesIO()
    Image.new("RGB", (2, 2), (90, 130, 80)).save(output, format="PNG")
    uploaded = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": other_ip.json()["id"], "name": "外部背景", "type": "background"},
        files={"file": ("background.png", output.getvalue(), "image/png")},
    )
    assert uploaded.status_code == 201
    asset_version_id = uploaded.json()["asset_version_id"]
    approved = client.post(
        f"/api/v1/assets/{uploaded.json()['asset_id']}/versions/{asset_version_id}/approve",
        params={"ip_id": other_ip.json()["id"]},
    )
    assert approved.status_code == 200
    document = build_document(episode_id, brand_version_id)
    document["pages"][0]["panels"][0]["elements"].append({
        "id": str(uuid4()),
        "type": "image",
        "asset_version_id": asset_version_id,
        "transform": {"x": 0, "y": 0, "width": 200, "height": 200, "rotation": 0},
        "crop": {"x": 0, "y": 0, "width": 1, "height": 1},
        "opacity": 1,
        "z_index": 1,
        "locked": False,
    })

    response = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": document},
    )

    assert response.status_code == 404
