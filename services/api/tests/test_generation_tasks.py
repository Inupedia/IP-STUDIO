from collections.abc import Iterator
from io import BytesIO
import json
from uuid import uuid4
from zipfile import ZipFile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (2, 2), (24, 100, 180, 200)).save(output, format="PNG")
    return output.getvalue()


@pytest.fixture
def client(tmp_path) -> Iterator[TestClient]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'generation-test.db'}",
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
        json={"number": 1, "title": "在吗？"},
    )
    assert ip.status_code == series.status_code == episode.status_code == 201
    return ip.json()["id"], episode.json()["id"]


def approved_asset(client: TestClient, ip_id: str) -> dict[str, object]:
    uploaded = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": "角色参考", "type": "character_reference"},
        files={"file": ("ref.png", image_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201, uploaded.text
    result = uploaded.json()
    approved = client.post(
        f"/api/v1/assets/{result['asset_id']}/versions/{result['asset_version_id']}/approve",
        params={"ip_id": ip_id},
    )
    assert approved.status_code == 200, approved.text
    return result


def approved_bibles(client: TestClient, ip_id: str, asset_version_id: str) -> tuple[str, str]:
    character = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={
            "code": "KAZ",
            "name": "卡仔",
            "bible": {
                "personality": "慢热",
                "fixed_appearance": "圆脸、浅蓝色身体",
                "standard_reference_asset_version_ids": [asset_version_id],
            },
        },
    )
    assert character.status_code == 201, character.text
    character_id = character.json()["character_version_id"]
    assert client.post(f"/api/v1/character-versions/{character_id}/approve").status_code == 200

    style = client.post(
        f"/api/v1/ips/{ip_id}/styles",
        json={
            "name": "清爽漫画",
            "bible": {
                "linework_rules": ["干净线条"],
                "palette": {"主色": "浅蓝"},
                "positive_rules": ["留白充足"],
                "negative_rules": ["不要复杂背景"],
                "example_asset_version_ids": [asset_version_id],
            },
        },
    )
    assert style.status_code == 201, style.text
    style_id = style.json()["style_version_id"]
    assert client.post(f"/api/v1/style-versions/{style_id}/approve").status_code == 200
    assert client.put(
        f"/api/v1/ips/{ip_id}/default-style", json={"style_version_id": style_id}
    ).status_code == 200
    return character_id, style_id


def script(character_version_id: str) -> dict[str, object]:
    dialogue_id = str(uuid4())
    return {
        "schema_version": "1.0",
        "title": "在吗？",
        "summary": "朋友发来消息。",
        "theme_tags": ["日常"],
        "scenes": [{
            "scene_id": str(uuid4()),
            "name": "卧室",
            "location": "卡仔的卧室",
            "time": "夜晚",
            "action": "卡仔低头看手机。",
            "character_version_ids": [character_version_id],
            "dialogues": [{
                "dialogue_id": dialogue_id,
                "speaker_id": str(uuid4()),
                "speaker_name": "朋友",
                "text": "绝不应送进图像模型的消息：在吗？",
                "kind": "chat_message",
            }],
            "panels": [{
                "action_id": str(uuid4()),
                "action": "卡仔看见手机上的新消息。",
                "shot_type": "close_up",
                "character_version_ids": [character_version_id],
                "background_asset_version_id": None,
                "no_text_prompt": "卡仔低头看手机，画面内不要出现任何文字。",
                "dialogue_ids": [dialogue_id],
            }],
        }],
    }


def create_script(
    client: TestClient, episode_id: str, character_version_id: str
) -> tuple[int, str]:
    created = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "script": script(character_version_id)},
    )
    assert created.status_code == 201, created.text
    panel_id = created.json()["script"]["scenes"][0]["panels"][0]["action_id"]
    return created.json()["revision_no"], panel_id


def test_task_freezes_prompt_references_and_returns_safe_reference_bundle(
    client: TestClient,
) -> None:
    ip_id, episode_id = create_episode(client)
    asset = approved_asset(client, ip_id)
    character_version_id, style_version_id = approved_bibles(
        client, ip_id, asset["asset_version_id"]
    )
    revision_no, panel_id = create_script(client, episode_id, character_version_id)

    created = client.post(
        f"/api/v1/episodes/{episode_id}/generation-tasks",
        json={
            "script_revision_no": revision_no,
            "panel_id": panel_id,
            "reference_version_ids": [],
            "mode": "chatgpt_web",
        },
    )

    assert created.status_code == 201, created.text
    task = created.json()
    assert task["status"] == "prepared"
    assert task["mode"] == "chatgpt_web"
    assert str(character_version_id) in task["prompt_snapshot"]["text"]
    assert str(style_version_id) in task["prompt_snapshot"]["text"]
    assert "单格" in task["prompt_snapshot"]["text"]
    assert "页码" in task["prompt_snapshot"]["text"]
    assert "水印" in task["prompt_snapshot"]["text"]
    assert "绝不应送进图像模型" not in task["prompt_snapshot"]["text"]
    assert "在吗？" not in task["prompt_snapshot"]["text"]
    frozen_asset_ids = {
        item["version_id"]
        for item in task["reference_snapshot"]
        if item["kind"] == "asset_version"
    }
    assert frozen_asset_ids == {asset["asset_version_id"]}

    archive_response = client.get(task["reference_bundle_url"])
    assert archive_response.status_code == 200
    assert archive_response.headers["content-type"].startswith("application/zip")
    with ZipFile(BytesIO(archive_response.content)) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        image_path = f"assets/{asset['asset_version_id']}.png"
        assert image_path in archive.namelist()
        assert archive.read(image_path) == image_bytes()
        assert manifest["task_id"] == task["task_id"]
        assert manifest["locked_version_ids"]["character"] == [character_version_id]
        assert manifest["locked_version_ids"]["style"] == [style_version_id]

    waiting = client.post(f"/api/v1/generation-tasks/{task['task_id']}/waiting-manual-generation")
    assert waiting.status_code == 200, waiting.text
    next_style = client.post(
        f"/api/v1/ips/{ip_id}/styles",
        json={"name": "另一个画风", "bible": {"linework_rules": ["粗线条"]}},
    )
    assert next_style.status_code == 201, next_style.text
    next_style_id = next_style.json()["style_version_id"]
    assert client.post(f"/api/v1/style-versions/{next_style_id}/approve").status_code == 200
    assert client.put(
        f"/api/v1/ips/{ip_id}/default-style",
        json={"style_version_id": next_style_id},
    ).status_code == 200
    read_back = client.get(f"/api/v1/generation-tasks/{task['task_id']}")

    assert read_back.status_code == 200
    assert read_back.json()["status"] == "waiting_manual_generation"
    assert read_back.json()["prompt_snapshot"] == task["prompt_snapshot"]
    frozen_style_ids = [
        reference["version_id"]
        for reference in read_back.json()["reference_snapshot"]
        if reference["kind"] == "style_version"
    ]
    assert frozen_style_ids == [style_version_id]
    assert client.post(
        f"/api/v1/generation-tasks/{task['task_id']}/waiting-manual-generation"
    ).status_code == 409


def test_references_must_be_approved_and_belong_to_episode_ip(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client, "OWNER")
    other_ip_id, _ = create_episode(client, "OTHER")
    owner_asset = approved_asset(client, ip_id)
    foreign_asset = approved_asset(client, other_ip_id)
    character_version_id, _style_version_id = approved_bibles(
        client, ip_id, owner_asset["asset_version_id"]
    )
    foreign_character_version_id, foreign_style_version_id = approved_bibles(
        client, other_ip_id, foreign_asset["asset_version_id"]
    )
    revision_no, panel_id = create_script(client, episode_id, character_version_id)

    def create_with_reference(reference_version_id: str):
        return client.post(
            f"/api/v1/episodes/{episode_id}/generation-tasks",
            json={
                "script_revision_no": revision_no,
                "panel_id": panel_id,
                "reference_version_ids": [reference_version_id],
                "mode": "chatgpt_web",
            },
        )

    cross_ip_asset = create_with_reference(foreign_asset["asset_version_id"])
    cross_ip_character = create_with_reference(foreign_character_version_id)
    cross_ip_style = create_with_reference(foreign_style_version_id)
    unapproved_asset = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": "候选图", "type": "character_reference"},
        files={"file": ("candidate.png", image_bytes(), "image/png")},
    )
    unapproved_character = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={"code": "CAND", "name": "候选角色", "bible": {"fixed_appearance": "圆脸"}},
    )
    unapproved_style = client.post(
        f"/api/v1/ips/{ip_id}/styles",
        json={"name": "候选画风", "bible": {"linework_rules": ["干净线条"]}},
    )
    unapproved_asset_task = create_with_reference(unapproved_asset.json()["asset_version_id"])
    unapproved_character_task = create_with_reference(
        unapproved_character.json()["character_version_id"]
    )
    unapproved_style_task = create_with_reference(unapproved_style.json()["style_version_id"])
    unsupported = client.post(
        f"/api/v1/episodes/{episode_id}/generation-tasks",
        json={
            "script_revision_no": revision_no,
            "panel_id": panel_id,
            "reference_version_ids": [],
            "mode": "codex_native",
        },
    )

    assert (
        cross_ip_asset.status_code
        == cross_ip_character.status_code
        == cross_ip_style.status_code
        == 404
    )
    assert unapproved_asset_task.status_code == 409
    assert unapproved_character_task.status_code == 409
    assert unapproved_style_task.status_code == 409
    assert unsupported.status_code == 422
