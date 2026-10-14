from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.models.ip import IP
from app.models.workspace import Workspace
from app.main import create_app

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
    )
    with TestClient(application) as test_client:
        token_response = test_client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert token_response.status_code == 200
        test_client.headers["Authorization"] = f"Bearer {token_response.json()['access_token']}"
        yield test_client


def test_ip_list_requires_authenticated_admin() -> None:
    response = TestClient(create_app()).get("/api/v1/ips")

    assert response.status_code == 401


def test_duplicate_ip_code_rejected(client: TestClient) -> None:
    first = client.post("/api/v1/ips", json={"code": "lag", "name": "人间卡顿局"})
    duplicate = client.post("/api/v1/ips", json={"code": "LAG", "name": "另一个名字"})

    assert first.status_code == 201
    assert first.json()["code"] == "LAG"
    assert duplicate.status_code == 409


def test_episode_number_unique(client: TestClient) -> None:
    ip_response = client.post("/api/v1/ips", json={"code": "LAG", "name": "人间卡顿局"})
    assert ip_response.status_code == 201

    series_response = client.post(
        "/api/v1/series",
        json={"ip_id": ip_response.json()["id"], "name": "日常卡顿"},
    )
    assert series_response.status_code == 201
    series_id = series_response.json()["id"]

    first = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={"number": 1, "title": "在吗"},
    )
    duplicate = client.post(
        f"/api/v1/series/{series_id}/episodes",
        json={"number": 1, "title": "重复编号"},
    )

    assert first.status_code == 201
    assert duplicate.status_code == 409


def test_other_workspace_not_visible(client: TestClient) -> None:
    own_response = client.post("/api/v1/ips", json={"code": "OWN", "name": "我的 IP"})
    assert own_response.status_code == 201

    with client.app.state.session_factory.begin() as session:
        other_workspace = Workspace(name="Other workspace")
        session.add(other_workspace)
        session.flush()
        other_ip = IP(workspace_id=other_workspace.id, code="SECRET", name="私有 IP")
        session.add(other_ip)
        session.flush()
        other_ip_id = str(other_ip.id)

    own_read = client.get(f"/api/v1/ips/{own_response.json()['id']}")
    other_read = client.get(f"/api/v1/ips/{other_ip_id}")

    assert own_read.status_code == 200
    assert other_read.status_code == 404


def test_invalid_admin_password_is_rejected(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/token",
        data={"username": TEST_EMAIL, "password": "incorrect-password"},
    )

    assert response.status_code == 401
