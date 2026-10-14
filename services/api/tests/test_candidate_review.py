from collections.abc import Iterator
from io import BytesIO
from uuid import uuid4

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


def image_bytes(color: tuple[int, int, int, int]) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (3, 2), color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'candidate-review-test.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
    )
    with TestClient(application) as test_client:
        token = test_client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert token.status_code == 200
        test_client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        yield test_client


def create_episode(client: TestClient, code: str = "LAG") -> tuple[str, str]:
    ip = client.post("/api/v1/ips", json={"code": code, "name": f"IP {code}"})
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "日常"})
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "第一格"},
    )
    assert ip.status_code == series.status_code == episode.status_code == 201
    return ip.json()["id"], episode.json()["id"]


def create_waiting_task(client: TestClient, episode_id: str) -> tuple[str, str]:
    panel_id = str(uuid4())
    script = {
        "schema_version": "1.0",
        "title": "第一格",
        "summary": "用于候选审核测试。",
        "theme_tags": [],
        "scenes": [{
            "scene_id": str(uuid4()),
            "name": "场景",
            "location": "室内",
            "time": "白天",
            "action": "角色站立。",
            "character_version_ids": [],
            "dialogues": [],
            "panels": [{
                "action_id": panel_id,
                "action": "角色站立。",
                "shot_type": "medium",
                "character_version_ids": [],
                "background_asset_version_id": None,
                "no_text_prompt": "无字画面。",
                "dialogue_ids": [],
            }],
        }],
    }
    history = client.get(f"/api/v1/episodes/{episode_id}/scripts")
    base_revision = history.json()[0]["revision_no"] if history.json() else 0
    revision_no = base_revision + 1
    script_revision = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": base_revision, "script": script},
    )
    assert script_revision.status_code == 201, script_revision.text
    task = client.post(
        f"/api/v1/episodes/{episode_id}/generation-tasks",
        json={
            "script_revision_no": revision_no,
            "panel_id": panel_id,
            "reference_version_ids": [],
            "mode": "chatgpt_web",
        },
    )
    assert task.status_code == 201, task.text
    task_id = task.json()["task_id"]
    waiting = client.post(f"/api/v1/generation-tasks/{task_id}/waiting-manual-generation")
    assert waiting.status_code == 200, waiting.text
    return task_id, panel_id


def import_candidate(client: TestClient, ip_id: str, task_id: str, color: tuple[int, int, int, int]):
    uploaded = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": "待审核画格", "type": "composite_panel"},
        files={"file": ("panel.png", image_bytes(color), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    imported = client.post(
        f"/api/v1/generation-tasks/{task_id}/candidates",
        json={"asset_version_id": uploaded.json()["asset_version_id"]},
    )
    assert imported.status_code == 201, imported.text
    return uploaded.json(), imported.json()


def test_rejected_candidate_is_archived_and_cannot_be_bound_again(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    task_id, panel_id = create_waiting_task(client, episode_id)
    uploaded, candidate = import_candidate(client, ip_id, task_id, (90, 40, 200, 255))

    review = client.get(f"/api/v1/ips/{ip_id}/generation-candidates")
    rejected = client.post(
        f"/api/v1/generation-candidates/{candidate['candidate_id']}/reject",
        json={"review_note": "角色比例不符合设定"},
    )
    repeated_rejection = client.post(
        f"/api/v1/generation-candidates/{candidate['candidate_id']}/reject",
        json={"review_note": "重复审核不能覆盖原记录"},
    )
    version = client.get(
        f"/api/v1/assets/{uploaded['asset_id']}",
        params={"ip_id": ip_id},
    )
    retry_task_id, _ = create_waiting_task(client, episode_id)
    rebound = client.post(
        f"/api/v1/generation-tasks/{retry_task_id}/candidates",
        json={"asset_version_id": uploaded["asset_version_id"]},
    )
    history = client.get(f"/api/v1/ips/{ip_id}/generation-candidates")

    assert review.status_code == 200
    assert review.json()[0]["status"] == "pending_review"
    assert review.json()[0]["panel_id"] == panel_id
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    assert rejected.json()["review_note"] == "角色比例不符合设定"
    assert rejected.json()["reviewed_by_user_id"] is not None
    assert rejected.json()["reviewed_at"] is not None
    assert repeated_rejection.status_code == 409
    assert version.json()["status"] == "archived"
    assert rebound.status_code == 409
    assert len(history.json()) == 1
    assert history.json()[0]["status"] == "rejected"


def test_approved_candidate_becomes_a_reusable_approved_asset(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    task_id, _panel_id = create_waiting_task(client, episode_id)
    uploaded, candidate = import_candidate(client, ip_id, task_id, (40, 170, 70, 255))

    bypass = client.post(
        f"/api/v1/assets/{uploaded['asset_id']}/versions/{uploaded['asset_version_id']}/approve",
        params={"ip_id": ip_id},
    )
    approved = client.post(f"/api/v1/generation-candidates/{candidate['candidate_id']}/approve")
    version = client.get(
        f"/api/v1/assets/{uploaded['asset_id']}",
        params={"ip_id": ip_id},
    )
    assets = client.get("/api/v1/assets", params={"ip_id": ip_id})

    assert bypass.status_code == 409
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["reviewed_by_user_id"] is not None
    assert version.json()["status"] == "approved"
    assert any(asset["asset_version_id"] == uploaded["asset_version_id"] for asset in assets.json())
    assert all(asset["status"] == "approved" for asset in assets.json())
