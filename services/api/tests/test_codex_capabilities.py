import json
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from PIL import Image

from app.codex.capabilities import (
    CapabilityReport,
    ImageGenerationProbeResult,
    probe_capabilities,
    run_image_generation_probe,
)
from app.config import Settings
from app.main import create_app
from fastapi.testclient import TestClient
from app.storage.local_blobs import ImageInfo
from datetime import datetime, timezone

TEST_EMAIL = "codex-admin@example.test"
TEST_PASSWORD = "test-password-long-enough"
TEST_SECRET = "test-signing-secret-with-at-least-thirty-two-bytes"


def test_settings_read_configured_imagegen_executable(monkeypatch) -> None:
    monkeypatch.setenv("IP_STUDIO_CODEX_IMAGEGEN_EXECUTABLE", "/opt/codex-imagegen/codex")

    settings = Settings(_env_file=None)

    assert settings.codex_imagegen_executable_path == Path("/opt/codex-imagegen/codex")


def png_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (4, 3), (100, 180, 120)).save(buffer, format="PNG")
    return buffer.getvalue()


def test_missing_codex_reports_unavailable() -> None:
    report = probe_capabilities(executable_lookup=lambda _name: None)

    assert report.status == "unavailable"
    assert "Codex CLI" in report.reason
    assert report.codex_path is None
    assert report.image_generation_advertised is False


def test_configured_codex_path_takes_precedence_over_path_lookup(tmp_path) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    executable.chmod(0o755)
    lookup_calls: list[str] = []

    def command_runner(args: list[str], **_kwargs: object) -> SimpleNamespace:
        if "login" in args:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr="")
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.163.0", stderr="")

    report = probe_capabilities(
        configured_codex_path=executable,
        executable_lookup=lambda name: lookup_calls.append(name) or "/opt/homebrew/bin/codex",
        command_runner=command_runner,
        app_server_probe=lambda _path: {"imageGeneration": True},
    )

    assert report.codex_path == str(executable.resolve())
    assert report.codex_version == "codex-cli 0.163.0"
    assert lookup_calls == []


def test_invalid_configured_codex_path_does_not_fall_back_to_path(tmp_path) -> None:
    lookup_calls: list[str] = []
    report = probe_capabilities(
        configured_codex_path=tmp_path / "missing-codex",
        executable_lookup=lambda name: lookup_calls.append(name) or "/opt/homebrew/bin/codex",
    )

    assert report.status == "unavailable"
    assert report.codex_path is None
    assert "配置的 Codex ImageGen 可执行文件不可用" in report.reason
    assert lookup_calls == []


def test_skill_present_but_imagegen_unavailable() -> None:
    def command_runner(_args: list[str], **_kwargs: object) -> SimpleNamespace:
        if "login" in _args:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr="")
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.162.1", stderr="")

    report = probe_capabilities(
        executable_lookup=lambda _name: "/opt/codex",
        command_runner=command_runner,
        app_server_probe=lambda _path: {"imageGeneration": False, "webSearch": True},
    )

    assert report.status == "unsupported"
    assert report.image_generation_advertised is False
    assert report.e2e_verified is False
    assert "未暴露 ImageGen" in report.reason


def test_advertised_imagegen_is_not_available_until_real_png_probe_passes() -> None:
    def command_runner(_args: list[str], **_kwargs: object) -> SimpleNamespace:
        if "login" in _args:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr="")
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.162.1", stderr="")

    report = probe_capabilities(
        executable_lookup=lambda _name: "/opt/codex",
        command_runner=command_runner,
        app_server_probe=lambda _path: {"imageGeneration": True, "webSearch": True},
    )

    assert report.status == "unavailable"
    assert report.image_generation_advertised is True
    assert report.e2e_verified is False
    assert "真实 PNG" in report.reason


def test_successful_png_probe_is_bound_to_the_same_codex_installation() -> None:
    def command_runner(_args: list[str], **_kwargs: object) -> SimpleNamespace:
        if "login" in _args:
            return SimpleNamespace(returncode=0, stdout="Logged in using ChatGPT", stderr="")
        return SimpleNamespace(returncode=0, stdout="codex-cli 0.162.1", stderr="")

    matching = probe_capabilities(
        executable_lookup=lambda _name: "/opt/codex",
        command_runner=command_runner,
        app_server_probe=lambda _path: {"imageGeneration": True},
        e2e_verified=True,
        verified_codex_path="/opt/codex",
        verified_codex_version="codex-cli 0.162.1",
    )
    stale = probe_capabilities(
        executable_lookup=lambda _name: "/opt/codex",
        command_runner=command_runner,
        app_server_probe=lambda _path: {"imageGeneration": True},
        e2e_verified=True,
        verified_codex_path="/old/codex",
        verified_codex_version="codex-cli 0.162.1",
    )

    assert matching.status == "available"
    assert matching.e2e_verified is True
    assert stale.status == "unavailable"
    assert stale.e2e_verified is False


def test_needs_auth_is_reported_without_querying_app_server() -> None:
    def command_runner(_args: list[str], **_kwargs: object) -> SimpleNamespace:
        return SimpleNamespace(returncode=1, stdout="Not logged in", stderr="")

    app_server_called = False

    def app_server_probe(_path: str) -> dict[str, bool]:
        nonlocal app_server_called
        app_server_called = True
        return {"imageGeneration": True}

    report = probe_capabilities(
        executable_lookup=lambda _name: "/opt/codex",
        command_runner=command_runner,
        app_server_probe=app_server_probe,
    )

    assert report.status == "needs_auth"
    assert app_server_called is False


def test_explicit_imagegen_probe_requires_native_image_event_and_decodable_png(tmp_path) -> None:
    def command_runner(args: list[str], **kwargs: object) -> SimpleNamespace:
        work_dir = Path(args[args.index("-C") + 1])
        (work_dir / "probe.png").write_bytes(png_bytes())
        stdout = kwargs["stdout"]
        assert hasattr(stdout, "write")
        stdout.write(json.dumps({
            "type": "item.completed",
            "item": {"type": "imageGeneration", "status": "completed"},
        }) + "\n")
        return SimpleNamespace(returncode=0)

    result = run_image_generation_probe(
        "/opt/codex",
        temp_root=tmp_path,
        command_runner=command_runner,
    )

    assert result.verified is True
    assert result.image is not None
    assert result.image.mime == "image/png"
    assert result.image.width == 4
    assert result.image.height == 3


def test_image_file_without_native_generation_event_is_rejected(tmp_path) -> None:
    def command_runner(args: list[str], **kwargs: object) -> SimpleNamespace:
        work_dir = Path(args[args.index("-C") + 1])
        (work_dir / "probe.png").write_bytes(png_bytes())
        kwargs["stdout"].write(json.dumps({
            "type": "item.completed",
            "item": {"type": "agent_message", "text": "PNG generated."},
        }) + "\n")
        return SimpleNamespace(returncode=0)

    result = run_image_generation_probe(
        "/opt/codex",
        temp_root=tmp_path,
        command_runner=command_runner,
    )

    assert result.verified is False
    assert result.image is None
    assert "没有成功的原生 ImageGen" in result.reason


def test_capability_endpoint_is_admin_only_and_does_not_trigger_image_generation(
    tmp_path, monkeypatch
) -> None:
    configured_executable = tmp_path / "codex"
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'codex-capabilities.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
        codex_imagegen_executable_path=configured_executable,
    )
    called: list[dict[str, object]] = []

    def fake_probe(**kwargs: object) -> SimpleNamespace:
        called.append(kwargs)
        return SimpleNamespace(
            status="unavailable",
            reason="需要真实 PNG 探测",
            codex_path="/opt/codex",
            codex_version="codex-cli 0.1.0",
            app_server_available=True,
            image_generation_advertised=True,
            e2e_verified=False,
            checked_at="2026-10-14T00:00:00Z",
        )

    monkeypatch.setattr("app.api.codex.probe_capabilities", fake_probe)

    with TestClient(application) as client:
        unauthorized = client.get("/api/v1/codex/capabilities")
        token = client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        report = client.get("/api/v1/codex/capabilities")

    assert unauthorized.status_code == 401
    assert report.status_code == 200
    assert report.json()["status"] == "unavailable"
    assert called == [{
        "configured_codex_path": configured_executable,
        "e2e_verified": False,
        "verified_codex_path": None,
        "verified_codex_version": None,
    }]


def test_explicit_probe_endpoint_runs_e2e_and_caches_only_validated_result(tmp_path, monkeypatch) -> None:
    configured_executable = tmp_path / "codex"
    application = create_app(
        database_url=f"sqlite:///{tmp_path / 'codex-e2e-probe.db'}",
        jwt_secret_key=TEST_SECRET,
        bootstrap_admin_email=TEST_EMAIL,
        bootstrap_admin_password=TEST_PASSWORD,
        initialize_schema=True,
        asset_storage_dir=tmp_path / "blobs",
        codex_imagegen_executable_path=configured_executable,
    )
    base_report = CapabilityReport(
        status="unavailable",
        reason="provider 已声明；尚未验证真实 PNG。",
        codex_path="/opt/codex",
        codex_version="codex-cli 0.162.1",
        app_server_available=True,
        image_generation_advertised=True,
        e2e_verified=False,
        checked_at=datetime.now(timezone.utc),
    )
    probe_calls: list[str] = []

    def fake_probe(**kwargs: object) -> CapabilityReport:
        assert kwargs["configured_codex_path"] == configured_executable
        verified = kwargs.get("e2e_verified") is True
        return base_report.model_copy(update={
            "status": "available" if verified else "unavailable",
            "reason": "PNG 已验证" if verified else base_report.reason,
            "e2e_verified": verified,
        })

    def fake_run_image_probe(codex_path: str) -> ImageGenerationProbeResult:
        probe_calls.append(codex_path)
        return ImageGenerationProbeResult(
            verified=True,
            reason="原生 ImageGen 工具已生成并解码出有效 PNG。",
            image=ImageInfo("a" * 64, "image/png", 40, 4, 3, False),
        )

    monkeypatch.setattr("app.api.codex.probe_capabilities", fake_probe)
    monkeypatch.setattr("app.api.codex.run_image_generation_probe", fake_run_image_probe)

    with TestClient(application) as client:
        token = client.post(
            "/api/v1/auth/token",
            data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        )
        client.headers["Authorization"] = f"Bearer {token.json()['access_token']}"
        response = client.post("/api/v1/codex/capabilities/probe")
        cached = client.get("/api/v1/codex/capabilities")

    assert response.status_code == 200
    assert response.json()["status"] == "available"
    assert response.json()["e2e_verified"] is True
    assert cached.json()["e2e_verified"] is True
    assert probe_calls == ["/opt/codex"]
    assert application.state.codex_imagegen_verified_path == "/opt/codex"
    assert application.state.codex_imagegen_verified_version == "codex-cli 0.162.1"

