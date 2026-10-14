from collections.abc import Iterator
import hashlib
from io import BytesIO
import json
from pathlib import Path
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi.testclient import TestClient
from PIL import Image
import pytest

from app.main import create_app
from app.codex.image_result import ImageResultError, validate_image_result
from app.codex.capabilities import CapabilityReport
from app.codex.adapter import generate_image

TEST_EMAIL = "codex-run-admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


def png_bytes(color: tuple[int, int, int, int] = (20, 120, 180, 255)) -> bytes:
    output = BytesIO()
    Image.new("RGBA", (5, 4), color).save(output, format="PNG")
    return output.getvalue()


def _create_task(client: TestClient) -> tuple[str, str]:
    ip = client.post("/api/v1/ips", json={"code": "RUN", "name": "ImageGen IP"})
    series = client.post("/api/v1/series", json={"ip_id": ip.json()["id"], "name": "测试系列"})
    episode = client.post(
        f"/api/v1/series/{series.json()['id']}/episodes",
        json={"number": 1, "title": "测试分集"},
    )
    panel_id = str(uuid4())
    script = {
        "schema_version": "1.0",
        "title": "测试分集",
        "summary": "Codex run integration fixture.",
        "theme_tags": [],
        "scenes": [{
            "scene_id": str(uuid4()),
            "name": "室内",
            "location": "房间",
            "time": "白天",
            "action": "角色站在桌边。",
            "character_version_ids": [],
            "dialogues": [],
            "panels": [{
                "action_id": panel_id,
                "action": "角色站在桌边。",
                "shot_type": "medium",
                "character_version_ids": [],
                "background_asset_version_id": None,
                "no_text_prompt": "纯画面，没有字。",
                "dialogue_ids": [],
            }],
        }],
    }
    revision = client.post(
        f"/api/v1/episodes/{episode.json()['id']}/scripts",
        json={"base_revision": 0, "script": script},
    )
    assert ip.status_code == series.status_code == episode.status_code == 201
    assert revision.status_code == 201, revision.text
    task = client.post(
        f"/api/v1/episodes/{episode.json()['id']}/generation-tasks",
        json={
            "script_revision_no": revision.json()["revision_no"],
            "panel_id": panel_id,
            "reference_version_ids": [],
            "mode": "chatgpt_web",
        },
    )
    assert task.status_code == 201, task.text
    return ip.json()["id"], task.json()["task_id"]


@pytest.fixture
def environment(tmp_path, monkeypatch) -> Iterator[tuple[TestClient, str, str]]:
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'codex-runs.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
    )
    application.state.codex_imagegen_verified_path = "/opt/codex"
    application.state.codex_imagegen_verified_version = "codex-cli 0.162.1"
    monkeypatch.setattr("app.api.codex_runs.probe_capabilities", lambda **_kwargs: CapabilityReport(
        status="available",
        reason="测试已验证",
        codex_path="/opt/codex",
        codex_version="codex-cli 0.162.1",
        app_server_available=True,
        image_generation_advertised=True,
        e2e_verified=True,
        checked_at="2026-10-14T00:00:00Z",
    ))
    with TestClient(application) as client:
        token = client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        assert token.status_code == 200
        client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        ip_id, task_id = _create_task(client)
        yield client, ip_id, task_id


def test_valid_png_is_imported_as_an_unreviewed_candidate(environment, monkeypatch) -> None:
    client, ip_id, task_id = environment

    def generate_image(_codex_path: str, _prompt: str, _bundle: bytes, job_dir: Path):
        output = job_dir / "result.png"
        output.write_bytes(png_bytes())
        return validate_image_result(output, job_dir)

    monkeypatch.setattr("app.services.codex_runs.generate_image", generate_image)
    started = client.post(f"/api/v1/generation-tasks/{task_id}/codex-runs")
    run_id = started.json()["run_id"]
    run = client.get(f"/api/v1/codex-runs/{run_id}")
    candidates = client.get(f"/api/v1/ips/{ip_id}/generation-candidates")
    assets = client.get("/api/v1/assets", params={"ip_id": ip_id})

    assert started.status_code == 202, started.text
    assert run.json()["status"] == "candidate_ready"
    assert run.json()["candidate_id"] == candidates.json()[0]["candidate_id"]
    assert candidates.json()[0]["status"] == "pending_review"
    assert candidates.json()[0]["panel_id"] == run.json()["panel_id"]
    assert assets.json()[0]["status"] == "candidate"
    assert assets.json()[0]["source_type"] == "codex_native"


def test_missing_generation_output_fails_without_candidate_or_task_progress(environment, monkeypatch) -> None:
    client, ip_id, task_id = environment

    def generate_image(_codex_path: str, _prompt: str, _bundle: bytes, _job_dir: Path):
        raise ImageResultError("Codex did not produce an image")

    monkeypatch.setattr("app.services.codex_runs.generate_image", generate_image)
    started = client.post(f"/api/v1/generation-tasks/{task_id}/codex-runs")
    run = client.get(f"/api/v1/codex-runs/{started.json()['run_id']}")
    task = client.get(f"/api/v1/generation-tasks/{task_id}")
    candidates = client.get(f"/api/v1/ips/{ip_id}/generation-candidates")

    assert started.status_code == 202
    assert run.json()["status"] == "failed"
    assert "did not produce" in run.json()["error_reason"]
    assert task.json()["status"] == "prepared"
    assert candidates.json() == []


def test_generated_image_path_escape_is_rejected(tmp_path) -> None:
    allowed_dir = tmp_path / "job"
    allowed_dir.mkdir()
    outside = tmp_path / "outside.png"
    outside.write_bytes(png_bytes())

    with pytest.raises(ImageResultError, match="escapes"):
        validate_image_result(outside, allowed_dir)


def _reference_bundle(task_id: str) -> bytes:
    reference = png_bytes((10, 180, 80, 255))
    manifest = {
        "task_id": task_id,
        "assets": [{"path": "assets/reference.png", "sha256": hashlib.sha256(reference).hexdigest()}],
    }
    archive_buffer = BytesIO()
    with ZipFile(archive_buffer, "w", ZIP_DEFLATED) as archive:
        archive.writestr("assets/reference.png", reference)
        archive.writestr("manifest.json", json.dumps(manifest))
    return archive_buffer.getvalue()


def test_adapter_attaches_verified_references_and_requires_native_imagegen_event(
    tmp_path, monkeypatch
) -> None:
    task_id = str(uuid4())
    observed: dict[str, object] = {}

    class FakeProcess:
        returncode: int | None = None

        def __init__(self, command, *, cwd, stdout, **kwargs):
            observed["command"] = command
            observed["kwargs"] = kwargs
            observed["cwd"] = cwd
            stdout.write(json.dumps({
                "type": "item.completed",
                "item": {"type": "image_generation_call", "status": "completed"},
            }) + "\n")
            (Path(cwd) / "result.png").write_bytes(png_bytes())

        def wait(self, timeout=None):
            self.returncode = 0
            return 0

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr("app.codex.adapter.subprocess.Popen", FakeProcess)
    job_dir = tmp_path / f"run-{task_id}-fixture"
    generated = generate_image("/opt/codex", "无字画格", _reference_bundle(task_id), job_dir)

    command = observed["command"]
    assert generated.image.mime == "image/png"
    assert any(str(argument).endswith("assets/reference.png") for argument in command)
    assert observed["cwd"] == job_dir.resolve()
    assert "shell" not in observed["kwargs"]
    assert (job_dir / "references/assets/reference.png").is_file()

    class NonNativeProcess(FakeProcess):
        def __init__(self, command, *, cwd, stdout, **kwargs):
            stdout.write(json.dumps({"type": "turn.completed", "item": {}}) + "\n")
            (Path(cwd) / "result.png").write_bytes(png_bytes())

    monkeypatch.setattr("app.codex.adapter.subprocess.Popen", NonNativeProcess)
    with pytest.raises(ImageResultError, match="native ImageGen"):
        generate_image("/opt/codex", "无字画格", _reference_bundle(task_id), tmp_path / f"run-{uuid4()}-non-native")


def test_admin_can_cancel_a_queued_run(environment, monkeypatch) -> None:
    client, _ip_id, task_id = environment
    monkeypatch.setattr("app.api.codex_runs.run_codex_generation", lambda *_args: None)
    started = client.post(f"/api/v1/generation-tasks/{task_id}/codex-runs")
    cancelled = client.post(f"/api/v1/codex-runs/{started.json()['run_id']}/cancel")

    assert started.status_code == 202
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "failed"
    assert cancelled.json()["error_reason"] == "已由管理员取消。"


def test_unavailable_codex_leaves_the_manual_chatgpt_flow_available(environment, monkeypatch) -> None:
    client, _ip_id, task_id = environment
    monkeypatch.setattr("app.api.codex_runs.probe_capabilities", lambda **_kwargs: CapabilityReport(
        status="unavailable",
        reason="测试环境无法连接本机 Codex",
        codex_path=None,
        codex_version=None,
        app_server_available=False,
        image_generation_advertised=False,
        e2e_verified=False,
        checked_at="2026-10-14T00:00:00Z",
    ))

    native = client.post(f"/api/v1/generation-tasks/{task_id}/codex-runs")
    manual = client.post(f"/api/v1/generation-tasks/{task_id}/waiting-manual-generation")

    assert native.status_code == 409
    assert "ChatGPT" in native.json()["detail"]
    assert manual.status_code == 200
    assert manual.json()["status"] == "waiting_manual_generation"
