from collections.abc import Iterator
import json
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def build_script(dialogue: str) -> dict[str, object]:
    dialogue_id = str(uuid4())
    return {
        "schema_version": "1.0",
        "title": "在吗？",
        "summary": "朋友发来消息，卡仔选择暂时不回应。",
        "theme_tags": ["日常", "聊天"],
        "scenes": [{
            "scene_id": str(uuid4()),
            "name": "卧室",
            "location": "卡仔的卧室",
            "time": "夜晚",
            "action": "卡仔低头看手机。",
            "character_version_ids": [],
            "dialogues": [{
                "dialogue_id": dialogue_id,
                "speaker_id": str(uuid4()),
                "speaker_name": "朋友",
                "text": dialogue,
                "kind": "chat_message",
                "sent_at": "21:30",
            }],
            "panels": [{
                "action_id": str(uuid4()),
                "action": "卡仔看见手机上的新消息。",
                "shot_type": "close_up",
                "character_version_ids": [],
                "background_asset_version_id": None,
                "no_text_prompt": "卡仔低头看手机，画面内不要出现任何文字。",
                "dialogue_ids": [dialogue_id],
            }],
        }],
    }


def add_bubble_dialogue(script: dict[str, object], text: str) -> tuple[dict[str, object], str]:
    scene = script["scenes"][0]
    dialogue_id = str(uuid4())
    scene["dialogues"].append({
        "dialogue_id": dialogue_id,
        "speaker_id": str(uuid4()),
        "speaker_name": "卡仔",
        "text": text,
        "kind": "speech_bubble",
    })
    scene["panels"][0]["dialogue_ids"].append(dialogue_id)
    return script, dialogue_id


def brand_shell() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "width": 1080,
        "height": 1440,
        "locked_elements": [{"id": "logo", "kind": "logo", "locked": True, "x": 30, "y": 30, "width": 100, "height": 50}],
        "dynamic_slots": {
            "title": {"x": 100, "y": 60, "width": 800, "height": 100},
            "episode_number": {"x": 900, "y": 40, "width": 120, "height": 50},
        },
    }


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
        token = test_client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert token.status_code == 200
        test_client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        yield test_client


def create_episode(client: TestClient) -> tuple[str, str]:
    ip = client.post("/api/v1/ips", json={"code": "LAG", "name": "人间卡顿局"})
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "日常"})
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "在吗？"},
    )
    assert ip.status_code == series.status_code == episode.status_code == 201
    return ip.json()["id"], episode.json()["id"]


def approve_brand(client: TestClient, ip_id: str) -> str:
    created = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates",
        json={"name": "固定外壳", "template": brand_shell()},
    )
    assert created.status_code == 201
    version_id = created.json()["brand_template_version_id"]
    approved = client.post(f"/api/v1/brand-template-versions/{version_id}/approve")
    assert approved.status_code == 200
    return version_id


def test_script_revision_is_immutable_and_new_edits_append(client: TestClient) -> None:
    _, episode_id = create_episode(client)
    first_script = build_script("在吗？")
    first = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "source_markdown": "朋友：在吗？", "script": first_script},
    )
    assert first.status_code == 201, first.text
    second_script = build_script("你在吗？")
    second = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 1, "source_markdown": "朋友：你在吗？", "script": second_script},
    )
    assert second.status_code == 201, second.text
    revision_one = client.get(f"/api/v1/episodes/{episode_id}/scripts/1")
    history = client.get(f"/api/v1/episodes/{episode_id}/scripts")

    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert revision_one.status_code == 200
    assert revision_one.json()["script"] == first.json()["script"]
    assert [item["revision_no"] for item in history.json()] == [2, 1]


def test_resync_requires_confirmation_before_changing_canvas_dialogue(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    brand_version_id = approve_brand(client, ip_id)
    canvas_document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    canvas_document["episode_id"] = episode_id
    canvas_document["brand_template_version_id"] = brand_version_id
    canvas_document["style_version_id"] = None
    for page in canvas_document["pages"]:
        page["brand_template_version_id"] = brand_version_id
        for panel in page["panels"]:
            panel["elements"] = [element for element in panel["elements"] if element["type"] != "image"]
    chat_message = next(
        element
        for element in canvas_document["pages"][0]["panels"][0]["elements"]
        if element["type"] == "chat_message"
    )
    chat_message["props"]["text"] = "旧台词"
    chat_message_id = chat_message["id"]
    bubble_id = str(uuid4())
    canvas_document["pages"][0]["panels"][0]["elements"].append({
        "id": bubble_id,
        "type": "speech_bubble",
        "props": {
            "text": "旧气泡",
            "shape": "rounded_rectangle",
            "fill": "#ffffff",
            "stroke": "#242923",
            "stroke_width": 2,
            "tail_position": "bottom",
            "font_family": "sans-serif",
            "font_size": 28,
        },
        "transform": {"x": 200, "y": 100, "width": 220, "height": 100, "rotation": 0},
        "opacity": 1,
        "z_index": 2,
        "locked": False,
    })
    saved_canvas = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 0, "document": canvas_document},
    )
    assert saved_canvas.status_code == 200, saved_canvas.text

    first_script_payload = add_bubble_dialogue(build_script("旧台词"), "旧气泡")[0]
    first_script = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "script": first_script_payload},
    )
    assert first_script.status_code == 201, first_script.text
    first_materialization = client.post(
        f"/api/v1/episodes/{episode_id}/scripts/{first_script.json()['revision_no']}/materialize",
        json={"base_document_revision": 1},
    )
    assert first_materialization.status_code == 200, first_materialization.text
    second_script_payload = add_bubble_dialogue(build_script("新台词"), "新气泡")[0]
    second_script = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 1, "script": second_script_payload},
    )
    assert second_script.status_code == 201, second_script.text
    refused = client.post(
        f"/api/v1/episodes/{episode_id}/scripts/{second_script.json()['revision_no']}/materialize",
        json={"base_document_revision": 1, "confirm_dialogue_sync": False},
    )
    unchanged = client.get(f"/api/v1/episodes/{episode_id}/document")
    confirmed = client.post(
        f"/api/v1/episodes/{episode_id}/scripts/{second_script.json()['revision_no']}/materialize",
        json={"base_document_revision": 1, "confirm_dialogue_sync": True},
    )
    updated = client.get(f"/api/v1/episodes/{episode_id}/document")

    assert refused.status_code == 409
    assert unchanged.json()["revision"] == 1
    unchanged_chat = next(
        element
        for element in unchanged.json()["document"]["pages"][0]["panels"][0]["elements"]
        if element["id"] == chat_message_id
    )
    unchanged_bubble = next(
        element
        for element in unchanged.json()["document"]["pages"][0]["panels"][0]["elements"]
        if element["id"] == bubble_id
    )
    assert unchanged_chat["props"]["text"] == "旧台词"
    assert unchanged_bubble["props"]["text"] == "旧气泡"
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["document_revision"] == 2
    assert confirmed.json()["synced_dialogue_count"] == 2
    updated_chat = next(
        element
        for element in updated.json()["document"]["pages"][0]["panels"][0]["elements"]
        if element["id"] == chat_message_id
    )
    updated_bubble = next(
        element
        for element in updated.json()["document"]["pages"][0]["panels"][0]["elements"]
        if element["id"] == bubble_id
    )
    assert updated_chat["props"]["text"] == "新台词"
    assert updated_bubble["props"]["text"] == "新气泡"


def test_script_character_references_must_be_approved_and_stay_in_the_episode_ip(client: TestClient) -> None:
    ip_id, episode_id = create_episode(client)
    other_ip = client.post("/api/v1/ips", json={"code": "PENG", "name": "噗噜"})
    assert other_ip.status_code == 201
    bible = {
        "personality": "热心",
        "language_style": "短句",
        "fixed_appearance": "圆脸",
        "invariants": [],
        "palette": {},
        "prohibited_features": [],
    }
    candidate = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={"code": "OWN", "name": "本 IP 角色", "bible": bible},
    )
    assert candidate.status_code == 201
    script = build_script("在吗？")
    script["scenes"][0]["character_version_ids"] = [candidate.json()["character_version_id"]]
    script["scenes"][0]["panels"][0]["character_version_ids"] = [candidate.json()["character_version_id"]]
    unapproved = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "script": script},
    )
    assert unapproved.status_code == 409
    approved = client.post(f"/api/v1/character-versions/{candidate.json()['character_version_id']}/approve")
    assert approved.status_code == 200

    foreign_character = client.post(
        f"/api/v1/ips/{other_ip.json()['id']}/characters",
        json={"code": "FOREIGN", "name": "外部角色", "bible": bible},
    )
    assert foreign_character.status_code == 201
    foreign_approval = client.post(
        f"/api/v1/character-versions/{foreign_character.json()['character_version_id']}/approve"
    )
    assert foreign_approval.status_code == 200
    script["scenes"][0]["character_version_ids"] = [foreign_character.json()["character_version_id"]]
    script["scenes"][0]["panels"][0]["character_version_ids"] = [foreign_character.json()["character_version_id"]]
    cross_ip = client.post(
        f"/api/v1/episodes/{episode_id}/scripts",
        json={"base_revision": 0, "script": script},
    )

    assert cross_ip.status_code == 404
