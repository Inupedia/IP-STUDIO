from collections.abc import Iterator
from copy import deepcopy
import json
import secrets
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.schemas.canvas import resolve_message_side

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = secrets.token_urlsafe(24)
TEST_SECRET = secrets.token_urlsafe(48)
CANVAS_FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'ip-studio-acceptance.db'}",
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


def create_brand(client: TestClient, ip_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates",
        json={
            "name": "卡仔固定外壳",
            "template": {
                "schema_version": "1.0",
                "width": 1080,
                "height": 1440,
                "locked_elements": [
                    {"id": "background", "kind": "background", "locked": True,
                     "x": 0, "y": 0, "width": 1080, "height": 1440, "fill": "#f4f0e8"},
                    {"id": "brand-mark", "kind": "logo", "locked": True,
                     "x": 48, "y": 40, "width": 120, "height": 60, "fill": "#243a2d"},
                    {"id": "footer", "kind": "footer", "locked": True,
                     "x": 48, "y": 1380, "width": 984, "height": 24, "fill": "#ded9ce"},
                ],
                "dynamic_slots": {
                    "title": {"x": 180, "y": 40, "width": 700, "height": 100},
                    "episode_number": {"x": 900, "y": 48, "width": 120, "height": 52},
                },
            },
        },
    )
    assert response.status_code == 201, response.text
    version_id = response.json()["brand_template_version_id"]
    approved = client.post(f"/api/v1/brand-template-versions/{version_id}/approve")
    assert approved.status_code == 200, approved.text
    return response.json()


def document_for(episode_id: str, brand_version_id: str, title: str, number: int) -> dict[str, object]:
    document = json.loads(CANVAS_FIXTURE.read_text(encoding="utf-8"))
    document["episode_id"] = episode_id
    document["brand_template_version_id"] = brand_version_id
    document["style_version_id"] = None
    document["revision"] = 0
    document["dynamic_fields"] = {"title": title, "episode_number": f"EP.{number:02d}"}
    for page in document["pages"]:
        page["id"] = str(uuid4())
        page["brand_template_version_id"] = brand_version_id
        for panel in page["panels"]:
            panel["id"] = str(uuid4())
            panel["elements"] = [
                {**element, "id": str(uuid4())}
                for element in panel["elements"]
                if element["type"] not in {"image", "sticker"}
            ]
    return document


def test_ep01_and_ep02_keep_one_approved_shell_and_dialogue_direction(client: TestClient) -> None:
    ip = client.post("/api/v1/ips", json={"code": "KAZI", "name": "人间卡顿局"})
    assert ip.status_code == 201, ip.text
    ip_id = ip.json()["id"]
    series = client.post("/api/v1/series", json={"ip_id": ip_id, "name": "加班日常"})
    assert series.status_code == 201, series.text
    episodes = [
        client.post(f"/api/v1/series/{series.json()['id']}/episodes", json={"number": 1, "title": "在吗？"}),
        client.post(f"/api/v1/series/{series.json()['id']}/episodes", json={"number": 2, "title": "今天又加班"}),
    ]
    assert all(episode.status_code == 201 for episode in episodes)
    ep01, ep02 = [episode.json() for episode in episodes]
    brand = create_brand(client, ip_id)
    version_id = brand["brand_template_version_id"]
    shell = client.get(f"/api/v1/brand-template-versions/{version_id}").json()["template"]

    documents = [
        document_for(ep01["id"], version_id, "在吗？", 1),
        document_for(ep02["id"], version_id, "今天又加班", 2),
    ]
    for episode, document in zip((ep01, ep02), documents, strict=True):
        saved = client.put(
            f"/api/v1/episodes/{episode['id']}/document",
            json={"base_revision": 0, "document": document},
        )
        assert saved.status_code == 200, saved.text
        assert saved.json()["revision"] == 1

    for episode, expected_title in ((ep01, "在吗？"), (ep02, "今天又加班")):
        current = client.get(f"/api/v1/episodes/{episode['id']}/document").json()
        saved_document = current["document"]
        assert current["revision"] == 1
        assert saved_document["brand_template_version_id"] == version_id
        assert saved_document["dynamic_fields"]["title"] == expected_title
        assert saved_document["pages"][0]["brand_template_version_id"] == version_id
        messages = [
            element
            for panel in saved_document["pages"][0]["panels"]
            for element in panel["elements"]
            if element["type"] == "chat_message"
        ]
        assert [message["props"]["text"] for message in messages] == ["在吗？", "不在。"]
        assert [
            resolve_message_side(message["props"]["sender_id"], message["props"]["self_participant_id"])
            for message in messages
        ] == ["left", "right"]
    assert client.get(f"/api/v1/brand-template-versions/{version_id}").json()["template"] == shell

    other_ip = client.post("/api/v1/ips", json={"code": "OTHER", "name": "其他 IP"}).json()
    other_brand = create_brand(client, other_ip["id"])
    cross_ip_update = deepcopy(client.get(f"/api/v1/episodes/{ep02['id']}/document").json()["document"])
    cross_ip_update["brand_template_version_id"] = other_brand["brand_template_version_id"]
    cross_ip_update["pages"][0]["brand_template_version_id"] = other_brand["brand_template_version_id"]
    rejected = client.put(
        f"/api/v1/episodes/{ep02['id']}/document",
        json={"base_revision": 1, "document": cross_ip_update},
    )
    assert rejected.status_code == 404
    assert client.get(f"/api/v1/episodes/{ep02['id']}/document").json()["document"]["brand_template_version_id"] == version_id
