from collections.abc import Iterator
from io import BytesIO
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.main import create_app

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


def image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGBA", (2, 2), (40, 80, 120, 255)).save(output, format="PNG")
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


def create_character(client: TestClient, ip_id: str, code: str, bible: dict) -> dict:
    response = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={"code": code, "name": f"角色 {code}", "bible": bible},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_style(client: TestClient, ip_id: str, name: str, bible: dict) -> dict:
    response = client.post(
        f"/api/v1/ips/{ip_id}/styles", json={"name": name, "bible": bible}
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_approved_character_is_immutable_and_can_be_derived(client: TestClient) -> None:
    ip_id = create_ip(client)
    initial_bible = {
        "personality": "慢半拍但热心",
        "language_style": "短句，偶尔冷幽默",
        "fixed_appearance": "圆脸，蓝色刘海",
        "invariants": ["左耳有小缺口"],
        "palette": {"primary": "#4388C7"},
        "prohibited_features": ["不能长出尾巴"],
    }
    first = create_character(client, ip_id, "KAZI", initial_bible)
    first_version_id = first["character_version_id"]
    approved = client.post(f"/api/v1/character-versions/{first_version_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert client.post(f"/api/v1/character-versions/{first_version_id}/approve").status_code == 409

    revised_bible = {**initial_bible, "language_style": "短句，偶尔一本正经地冷幽默"}
    second = client.post(
        f"/api/v1/characters/{first['character_id']}/versions",
        json={"base_version_id": first_version_id, "bible": revised_bible},
    )
    first_after = client.get(f"/api/v1/character-versions/{first_version_id}")

    assert second.status_code == 201
    assert second.json()["version_no"] == 2
    assert second.json()["status"] == "candidate"
    assert first_after.status_code == 200
    assert first_after.json()["bible"] == initial_bible
    assert first_after.json()["status"] == "approved"


def test_approved_style_is_immutable_and_can_be_derived(client: TestClient) -> None:
    ip_id = create_ip(client)
    initial_bible = {
        "linework_rules": ["线条清晰，粗细分层"],
        "palette": {"background": "#F4EAD7", "ink": "#242424"},
        "lighting": "柔和环境光",
        "materials": ["哑光纸感"],
        "aspect_ratios": ["3:4"],
        "positive_rules": ["角色颜色稳定"],
        "negative_rules": ["不要厚重写实阴影"],
        "font_rules": "中文使用清晰黑体",
        "speech_bubble_rules": "气泡线条保持简洁",
    }
    first = create_style(client, ip_id, "温暖漫画", initial_bible)
    first_version_id = first["style_version_id"]
    approved = client.post(f"/api/v1/style-versions/{first_version_id}/approve")
    assert approved.status_code == 200
    assert client.post(f"/api/v1/style-versions/{first_version_id}/approve").status_code == 409

    revised_bible = {**initial_bible, "lighting": "柔和的窗边环境光"}
    second = client.post(
        f"/api/v1/styles/{first['style_id']}/versions",
        json={"base_version_id": first_version_id, "bible": revised_bible},
    )
    first_after = client.get(f"/api/v1/style-versions/{first_version_id}")

    assert second.status_code == 201
    assert second.json()["version_no"] == 2
    assert second.json()["status"] == "candidate"
    assert first_after.json()["bible"] == initial_bible
    assert first_after.json()["status"] == "approved"


def test_unapproved_reference_rejected(client: TestClient) -> None:
    ip_id = create_ip(client)
    uploaded = client.post(
        "/api/v1/assets/upload",
        data={"ip_id": ip_id, "name": "官方参考", "type": "character_reference"},
        files={"file": ("ref.png", image_bytes(), "image/png")},
    )
    assert uploaded.status_code == 201
    asset_version_id = uploaded.json()["asset_version_id"]
    bible = {
        "personality": "热心",
        "language_style": "轻松",
        "fixed_appearance": "蓝色头发",
        "standard_reference_asset_version_ids": [asset_version_id],
    }

    rejected = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={"code": "REF", "name": "参考角色", "bible": bible},
    )

    assert rejected.status_code == 409
    approved_asset = client.post(
        f"/api/v1/assets/{uploaded.json()['asset_id']}/versions/{asset_version_id}/approve",
        params={"ip_id": ip_id},
    )
    assert approved_asset.status_code == 200
    accepted = client.post(
        f"/api/v1/ips/{ip_id}/characters",
        json={"code": "REF", "name": "参考角色", "bible": bible},
    )

    assert accepted.status_code == 201
    assert accepted.json()["bible"]["standard_reference_asset_version_ids"] == [asset_version_id]

    other_ip_id = create_ip(client, "OTHER")
    wrong_ip = client.post(
        f"/api/v1/ips/{other_ip_id}/characters",
        json={"code": "REF", "name": "不可跨 IP 引用", "bible": bible},
    )
    assert wrong_ip.status_code == 404


def test_default_style_requires_approved_style_for_same_ip(client: TestClient) -> None:
    ip_id = create_ip(client, "OWN")
    other_ip_id = create_ip(client, "OTHER")
    style = create_style(
        client,
        ip_id,
        "简笔画",
        {"linework_rules": ["线条稳定"], "positive_rules": ["干净留白"]},
    )
    version_id = style["style_version_id"]
    candidate = client.put(
        f"/api/v1/ips/{ip_id}/default-style", json={"style_version_id": version_id}
    )
    assert candidate.status_code == 409

    approved = client.post(f"/api/v1/style-versions/{version_id}/approve")
    assert approved.status_code == 200
    wrong_ip = client.put(
        f"/api/v1/ips/{other_ip_id}/default-style", json={"style_version_id": version_id}
    )
    correct_ip = client.put(
        f"/api/v1/ips/{ip_id}/default-style", json={"style_version_id": version_id}
    )

    assert wrong_ip.status_code == 404
    assert correct_ip.status_code == 200
    assert UUID(correct_ip.json()["default_style_version_id"]) == UUID(version_id)
