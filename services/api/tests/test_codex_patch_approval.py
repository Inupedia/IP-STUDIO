from collections.abc import Iterator
import json
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
import pytest

from app.main import create_app
from app.codex.patches import CanvasPatch

TEST_EMAIL = "patch-admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"
FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def brand_shell() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "width": 1080,
        "height": 1440,
        "locked_elements": [{
            "id": "locked-logo",
            "kind": "logo",
            "locked": True,
            "x": 30,
            "y": 30,
            "width": 100,
            "height": 50,
        }],
        "dynamic_slots": {
            "title": {"x": 100, "y": 60, "width": 800, "height": 100},
            "episode_number": {"x": 900, "y": 40, "width": 120, "height": 50},
        },
    }


@pytest.fixture
def environment(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, str, str]]:
    app = create_app(
        database_url=f"sqlite:///{tmp_path / 'codex-patch-approval.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
    )
    with TestClient(app) as client:
        token = client.post("/api/v1/auth/token", data={"username": TEST_EMAIL, "password": TEST_PASSWORD})
        assert token.status_code == 200
        client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        ip = client.post("/api/v1/ips", json={"code": "PATCH", "name": "Patch IP"})
        series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "测试系列"})
        episode = client.post(
            f"/api/v1/series/{series.json()['id']}/episodes",
            json={"number": 1, "title": "在吗？"},
        )
        template = client.post(
            f"/api/v1/ips/{ip.json()['id']}/brand-templates",
            json={"name": "固定外壳", "template": brand_shell()},
        )
        assert template.status_code == 201, template.text
        brand_version_id = template.json()["brand_template_version_id"]
        assert client.post(f"/api/v1/brand-template-versions/{brand_version_id}/approve").status_code == 200
        document = json.loads(FIXTURE.read_text(encoding="utf-8"))
        document["episode_id"] = episode.json()["id"]
        document["brand_template_version_id"] = brand_version_id
        document["style_version_id"] = None
        for page in document["pages"]:
            page["brand_template_version_id"] = brand_version_id
            page["panels"][0]["elements"] = [
                element for element in page["panels"][0]["elements"] if element["type"] != "image"
            ]
        saved = client.put(
            f"/api/v1/episodes/{episode.json()['id']}/document",
            json={"base_revision": 0, "document": document},
        )
        assert saved.status_code == 200, saved.text
        assert ip.status_code == series.status_code == episode.status_code == 201
        yield client, ip.json()["id"], episode.json()["id"]


def _install_proposer(monkeypatch) -> None:
    def propose_patch(*, instruction, document, scope, base_revision):
        return CanvasPatch(
            workspace_id=scope.workspace_id,
            ip_id=scope.ip_id,
            episode_id=scope.episode_id,
            document_id=scope.document_id,
            base_revision=base_revision,
            summary=instruction[:100],
            operations=[{
                "op": "set_text",
                "element_id": "00000000-0000-4000-8000-000000000010",
                "text": "候选对白",
            }],
        )

    monkeypatch.setattr("app.api.codex_patches.propose_patch", propose_patch)


def _create_proposal(client: TestClient, episode_id: str) -> dict[str, object]:
    response = client.post(
        f"/api/v1/episodes/{episode_id}/codex-patches",
        json={"instruction": "把朋友的消息改成候选对白"},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_rejected_patch_has_no_document_side_effects(environment, monkeypatch) -> None:
    client, _ip_id, episode_id = environment
    _install_proposer(monkeypatch)
    proposal = _create_proposal(client, episode_id)

    rejected = client.post(
        f"/api/v1/codex/patches/{proposal['patch_id']}/reject",
        json={"review_note": "不采用"},
    )
    current = client.get(f"/api/v1/episodes/{episode_id}/document")
    revisions = client.get(f"/api/v1/episodes/{episode_id}/revisions")

    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert current.json()["revision"] == 1
    assert current.json()["document"]["pages"][0]["panels"][0]["elements"][0]["props"]["text"] == "在吗？"
    assert [item["revision_no"] for item in revisions.json()] == [1]


def test_stale_revision_returns_409_without_overwriting_the_winner(environment, monkeypatch) -> None:
    client, _ip_id, episode_id = environment
    _install_proposer(monkeypatch)
    proposal = _create_proposal(client, episode_id)
    current = client.get(f"/api/v1/episodes/{episode_id}/document").json()["document"]
    current["dynamic_fields"]["title"] = "人工新版本"
    saved = client.put(
        f"/api/v1/episodes/{episode_id}/document",
        json={"base_revision": 1, "document": current},
    )

    applied = client.post(
        f"/api/v1/codex/patches/{proposal['patch_id']}/approve",
        json={"base_revision": 1, "approval_id": proposal["approval_id"]},
    )
    latest = client.get(f"/api/v1/episodes/{episode_id}/document")

    assert saved.status_code == 200
    assert applied.status_code == 409
    assert latest.json()["revision"] == 2
    assert latest.json()["document"]["dynamic_fields"]["title"] == "人工新版本"
    assert latest.json()["document"]["pages"][0]["panels"][0]["elements"][0]["props"]["text"] == "在吗？"


def test_approved_patch_is_applied_as_a_new_document_revision(environment, monkeypatch) -> None:
    client, _ip_id, episode_id = environment
    _install_proposer(monkeypatch)
    proposal = _create_proposal(client, episode_id)

    applied = client.post(
        f"/api/v1/codex/patches/{proposal['patch_id']}/approve",
        json={"base_revision": 1, "approval_id": proposal["approval_id"]},
    )
    current = client.get(f"/api/v1/episodes/{episode_id}/document")
    revisions = client.get(f"/api/v1/episodes/{episode_id}/revisions")

    assert applied.status_code == 200, applied.text
    assert applied.json()["status"] == "approved"
    assert applied.json()["applied_revision"] == 2
    assert current.json()["revision"] == 2
    assert current.json()["document"]["pages"][0]["panels"][0]["elements"][0]["props"]["text"] == "候选对白"
    assert [item["revision_no"] for item in revisions.json()] == [2, 1]
