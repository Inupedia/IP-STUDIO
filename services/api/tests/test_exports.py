from collections.abc import Iterator
from copy import deepcopy
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def page_png(size: tuple[int, int] = (1080, 1440), color: tuple[int, int, int] = (255, 255, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGB", size, color).save(output, format="PNG")
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


def create_episode(client: TestClient) -> tuple[str, str, str]:
    ip = client.post("/api/v1/ips", json={"code": "LAG", "name": "卡仔"})
    assert ip.status_code == 201, ip.text
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "日常"})
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
                    {"id": f"logo-{uuid4()}", "kind": "logo", "locked": True,
                     "x": 48, "y": 40, "width": 120, "height": 60, "fill": "#243a2d"}
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
    approved = client.post(f"/api/v1/brand-template-versions/{brand_version_id}/approve")
    assert approved.status_code == 200, approved.text
    return ip.json()["id"], episode.json()["id"], brand_version_id


def canvas_document(episode_id: str, brand_version_id: str) -> dict[str, object]:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["episode_id"] = episode_id
    document["brand_template_version_id"] = brand_version_id
    document["style_version_id"] = None
    document["dynamic_fields"] = {"title": "在吗？", "episode_number": "EP.01"}
    for page in document["pages"]:
        page["brand_template_version_id"] = brand_version_id
        for panel in page["panels"]:
            panel["elements"] = [
                element for element in panel["elements"]
                if element["type"] not in {"image", "sticker"}
            ]
    return document


def two_page_document(episode_id: str, brand_version_id: str) -> dict[str, object]:
    document = canvas_document(episode_id, brand_version_id)
    second_page = deepcopy(document["pages"][0])
    second_page["id"] = str(uuid4())
    second_page["order"] = 2
    for panel in second_page["panels"]:
        panel["id"] = str(uuid4())
        for element in panel["elements"]:
            element["id"] = str(uuid4())
    document["pages"].append(second_page)
    return document


def save_document(client: TestClient, episode_id: str, document: dict[str, object], base_revision: int = 0):
    return client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": base_revision, "document": document},
    )


def request_png_export(client: TestClient, episode_id: str, revision_no: int, pages: list[bytes]):
    return client.post(
        f"/api/v1/episodes/{episode_id}/export",
        data={"revision_no": str(revision_no)},
        files=[("pages", (f"ignored-{index}.png", data, "image/png")) for index, data in enumerate(pages, 1)],
    )


def test_png_export_preserves_original_dimensions_and_page_order(client: TestClient) -> None:
    _, episode_id, brand_version_id = create_episode(client)
    saved = save_document(client, episode_id, two_page_document(episode_id, brand_version_id))
    assert saved.status_code == 200, saved.text
    first_png = page_png(color=(220, 20, 60))
    second_png = page_png(color=(25, 80, 180))

    exported = request_png_export(client, episode_id, 1, [first_png, second_png])

    assert exported.status_code == 201, exported.text
    job = exported.json()
    assert job["status"] == "complete"
    assert job["format"] == "png_zip"
    assert job["revision_no"] == 1
    assert job["page_count"] == 2
    download = client.get(job["download_url"])
    assert download.status_code == 200
    with ZipFile(BytesIO(download.content)) as archive:
        assert archive.namelist() == ["page-01.png", "page-02.png"]
        for name, expected_color in zip(archive.namelist(), [(220, 20, 60), (25, 80, 180)], strict=True):
            with Image.open(BytesIO(archive.read(name))) as image:
                assert image.size == (1080, 1440)
                assert image.getpixel((0, 0)) == expected_color


def test_export_is_bound_to_an_immutable_document_revision(client: TestClient) -> None:
    _, episode_id, brand_version_id = create_episode(client)
    first_document = canvas_document(episode_id, brand_version_id)
    first_document["dynamic_fields"]["title"] = "第一版"
    first = save_document(client, episode_id, first_document)
    assert first.status_code == 200, first.text
    second_document = deepcopy(first_document)
    second_document["dynamic_fields"]["title"] = "第二版"
    second = save_document(client, episode_id, second_document, base_revision=1)
    assert second.status_code == 200, second.text

    exported = request_png_export(client, episode_id, 1, [page_png()])

    assert exported.status_code == 201, exported.text
    assert exported.json()["revision_no"] == 1
    assert client.get(f"/api/v1/exports/{exported.json()['id']}").json()["revision_no"] == 1


def test_export_rejects_page_count_or_dimensions_that_do_not_match_revision(client: TestClient) -> None:
    _, episode_id, brand_version_id = create_episode(client)
    saved = save_document(client, episode_id, two_page_document(episode_id, brand_version_id))
    assert saved.status_code == 200, saved.text

    missing_page = request_png_export(client, episode_id, 1, [page_png()])
    wrong_dimensions = request_png_export(client, episode_id, 1, [page_png((10, 10)), page_png()])

    assert missing_page.status_code == 422
    assert wrong_dimensions.status_code == 422
