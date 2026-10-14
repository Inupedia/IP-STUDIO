from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.services.templates import ResourceConflict, assert_template_shell_unchanged

TEST_EMAIL = "admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


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


def create_ip(client: TestClient, code: str) -> str:
    response = client.post("/api/v1/ips", json={"code": code, "name": f"IP {code}"})
    assert response.status_code == 201
    return response.json()["id"]


def shell(logo: str = "logo-v1") -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "width": 1080,
        "height": 1440,
        "locked_elements": [
            {
                "id": logo,
                "kind": "logo",
                "locked": True,
                "x": 44,
                "y": 40,
                "width": 100,
                "height": 48,
            }
        ],
        "dynamic_slots": {
            "title": {"x": 120, "y": 60, "width": 840, "height": 120},
            "episode_number": {"x": 930, "y": 30, "width": 100, "height": 50},
        },
    }


def test_brand_immutable_after_approval(client: TestClient) -> None:
    ip_id = create_ip(client, "LAG")
    created = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates",
        json={"name": "固定品牌外壳", "template": shell()},
    )
    assert created.status_code == 201, created.text
    first_id = created.json()["brand_template_version_id"]
    initial_template = created.json()["template"]

    approved = client.post(f"/api/v1/brand-template-versions/{first_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"

    next_shell = shell("logo-v2")
    derived = client.post(
        f"/api/v1/ips/{ip_id}/brand-templates/{created.json()['brand_template_id']}/versions",
        json={"base_version_id": first_id, "template": next_shell},
    )
    original = client.get(f"/api/v1/brand-template-versions/{first_id}")

    assert derived.status_code == 201, derived.text
    assert derived.json()["version_no"] == 2
    assert derived.json()["status"] == "candidate"
    assert original.status_code == 200
    assert original.json()["template"] == initial_template
    assert original.json()["status"] == "approved"
    assert client.post(f"/api/v1/brand-template-versions/{first_id}/approve").status_code == 409


def test_cross_ip_template_denied(client: TestClient) -> None:
    first_ip = create_ip(client, "LAG")
    second_ip = create_ip(client, "PENG")
    first = client.post(
        f"/api/v1/ips/{first_ip}/brand-templates",
        json={"name": "私有模板", "template": shell()},
    )
    assert first.status_code == 201
    foreign_derive = client.post(
        f"/api/v1/ips/{second_ip}/brand-templates/{first.json()['brand_template_id']}/versions",
        json={
            "base_version_id": first.json()["brand_template_version_id"],
            "template": shell("foreign-logo"),
        },
    )

    assert foreign_derive.status_code == 404


def test_locked_logo_edit_denied() -> None:
    approved_shell = shell()
    attempted_edit = shell("moved-logo")

    with pytest.raises(ResourceConflict, match="locked brand shell"):
        assert_template_shell_unchanged(approved_shell, attempted_edit)
