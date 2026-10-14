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
    Image.new("RGBA", (2, 2), color).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'candidate-test.db'}",
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


def create_episode(client: TestClient, code: str) -> tuple[str, str]:
    ip = client.post("/api/v1/ips", json={"code": code, "name": f"IP {code}"})
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "日常"})
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "第一格"},
    )
    assert ip.status_code == series.status_code == episode.status_code == 201
    return ip.json()["id"], episode.json()["id"]


def upload_candidate(client: TestClient, ip_id: str, color: tuple[int, int, int, int]):
    return client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": "生图候选", "type": "composite_panel"},
        files={"file": ("generated.png", image_bytes(color), "image/png")},
    )


def create_task(
    client: TestClient, episode_id: str, start_manual_generation: bool = True
) -> tuple[str, str]:
    panel_id = str(uuid4())
    script = {
        "schema_version": "1.0",
        "title": "第一格",
        "summary": "无对白的候选绑定测试。",
        "theme_tags": [],
        "scenes": [{
            "scene_id": str(uuid4()),
            "name": "场景",
            "location": "室内",
            "time": "白天",
            "action": "角色站在房间里。",
            "character_version_ids": [],
            "dialogues": [],
            "panels": [{
                "action_id": panel_id,
                "action": "角色站立。",
                "shot_type": "medium",
                "character_version_ids": [],
                "background_asset_version_id": None,
                "no_text_prompt": "无文字。",
                "dialogue_ids": [],
            }],
        }],
    }
    script_response = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "script": script},
    )
    assert script_response.status_code == 201, script_response.text
    task_response = client.post(
        f"/api/v1/episodes/{episode_id}/generation-tasks",
        json={
            "script_revision_no": 1,
            "panel_id": panel_id,
            "reference_version_ids": [],
            "mode": "chatgpt_web",
        },
    )
    assert task_response.status_code == 201, task_response.text
    task_id = task_response.json()["task_id"]
    if start_manual_generation:
        waiting = client.post(f"/api/v1/generation-tasks/{task_id}/waiting-manual-generation")
        assert waiting.status_code == 200, waiting.text
    return task_id, panel_id


def test_import_candidate_matches_task_ip_and_preserves_candidate_status(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client, "OWNER")
    task_id, panel_id = create_task(client, episode_id)
    uploaded = upload_candidate(client, ip_id, (20, 90, 160, 255))
    assert uploaded.status_code == 201, uploaded.text
    assert uploaded.json()["status"] == "candidate"
    asset_version_id = uploaded.json()["asset_version_id"]

    imported = client.post(
        f"/api/v1/generation-tasks/{task_id}/candidates",
        json={"asset_version_id": asset_version_id},
    )
    task = client.get(f"/api/v1/generation-tasks/{task_id}")
    duplicate = client.post(
        f"/api/v1/generation-tasks/{task_id}/candidates",
        json={"asset_version_id": asset_version_id},
    )

    assert imported.status_code == 201, imported.text
    assert imported.json()["task_id"] == task_id
    assert imported.json()["panel_id"] == panel_id
    assert imported.json()["asset_version_id"] == asset_version_id
    assert imported.json()["status"] == "pending_review"
    assert task.json()["status"] == "asset_imported"
    assert duplicate.status_code == 409
    deletion = client.delete(f"/api/v1/assets/{uploaded.json()['asset_id']}", params={"ip_id": ip_id, "confirm": True})
    assert deletion.status_code == 409


def test_candidate_cannot_attach_across_ip_or_before_manual_generation(client: TestClient) -> None:
    owner_ip_id, episode_id = create_episode(client, "OWNER")
    other_ip_id, _ = create_episode(client, "OTHER")
    task_id, _panel_id = create_task(client, episode_id)
    owner_candidate = upload_candidate(client, owner_ip_id, (15, 120, 210, 255))
    foreign_candidate = upload_candidate(client, other_ip_id, (210, 50, 30, 255))
    assert owner_candidate.status_code == foreign_candidate.status_code == 201

    foreign = client.post(
        f"/api/v1/generation-tasks/{task_id}/candidates",
        json={"asset_version_id": foreign_candidate.json()["asset_version_id"]},
    )
    prepared_ip_id, prepared_episode_id = create_episode(client, "PREPARED")
    prepared_task_id, _ = create_task(client, prepared_episode_id, start_manual_generation=False)
    prepared_candidate = upload_candidate(client, prepared_ip_id, (50, 150, 70, 255))
    assert prepared_candidate.status_code == 201
    before_start = client.post(
        f"/api/v1/generation-tasks/{prepared_task_id}/candidates",
        json={"asset_version_id": prepared_candidate.json()["asset_version_id"]},
    )

    assert foreign.status_code == 404
    assert before_start.status_code == 409
