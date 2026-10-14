"""Inspect the local Codex runtime without spending image-generation usage."""

from __future__ import annotations

import json
import queue
import shutil
import subprocess
import tempfile
import threading
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from app.storage.local_blobs import AssetValidationError, ImageInfo, inspect_image

CapabilityStatus = Literal["available", "unavailable", "needs_auth", "unsupported"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ExecutableLookup = Callable[[str], str | None]
AppServerProbe = Callable[[str], dict[str, object]]


class CapabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: CapabilityStatus
    reason: str
    codex_path: str | None
    codex_version: str | None
    app_server_available: bool
    image_generation_advertised: bool
    e2e_verified: bool
    checked_at: datetime


class ImageGenerationProbeResult(BaseModel):
    verified: bool
    reason: str
    image: ImageInfo | None


def _read_app_server_capabilities(codex_path: str, timeout_seconds: float = 12.0) -> dict[str, object]:
    """Ask the local public app-server protocol for provider capability flags."""
    process = subprocess.Popen(
        [codex_path, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1,
    )
    messages: queue.Queue[dict[str, object] | None] = queue.Queue()

    def collect_stdout() -> None:
        assert process.stdout is not None
        for line in process.stdout:
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                messages.put(message)
        messages.put(None)

    def drain_stderr() -> None:
        assert process.stderr is not None
        for _line in process.stderr:
            pass

    stdout_reader = threading.Thread(target=collect_stdout, daemon=True)
    stderr_reader = threading.Thread(target=drain_stderr, daemon=True)
    stdout_reader.start()
    stderr_reader.start()

    def send(message: dict[str, object]) -> None:
        if process.stdin is None:
            raise RuntimeError("Codex App Server input is unavailable")
        process.stdin.write(json.dumps(message, separators=(",", ":")) + "\n")
        process.stdin.flush()

    def response_for(request_id: int) -> dict[str, object]:
        try:
            while True:
                message = messages.get(timeout=timeout_seconds)
                if message is None:
                    raise RuntimeError("Codex App Server closed before replying")
                if message.get("id") == request_id:
                    if "error" in message:
                        raise RuntimeError("Codex App Server capability request failed")
                    result = message.get("result")
                    if not isinstance(result, dict):
                        raise RuntimeError("Codex App Server returned an invalid capability response")
                    return result
        except queue.Empty as error:
            raise TimeoutError("Codex App Server capability request timed out") from error

    try:
        send({
            "id": 1,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "ip-studio", "version": "0.1.0"},
            },
        })
        response_for(1)
        send({"method": "initialized"})
        send({"id": 2, "method": "modelProvider/capabilities/read", "params": {}})
        return response_for(2)
    finally:
        if process.stdin is not None:
            process.stdin.close()
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)


def _contains_image_generation_call(events_path: Path) -> bool:
    if not events_path.is_file() or events_path.stat().st_size > 16 * 1024 * 1024:
        return False
    with events_path.open(encoding="utf-8") as events_file:
        for line in events_file:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(event, dict) or event.get("type") not in {"item.completed", "item_complete"}:
                continue
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            item_type = item.get("type")
            item_status = str(item.get("status", "")).casefold()
            if item_type in {"imageGeneration", "image_generation_call"} and item_status in {
                "completed", "succeeded", "success",
            }:
                return True
            if item_type == "mcp_tool_call" and item_status in {"completed", "succeeded", "success"}:
                tool_name = " ".join(
                    str(item.get(key, ""))
                    for key in ("server", "tool", "tool_name", "title")
                ).casefold()
                if "imagegen" in tool_name or "image_gen" in tool_name or "image generation" in tool_name:
                    return True
    return False


def run_image_generation_probe(
    codex_path: str,
    *,
    temp_root: Path | None = None,
    command_runner: CommandRunner | None = None,
    timeout_seconds: int = 240,
) -> ImageGenerationProbeResult:
    """Run only after an explicit administrator action; no generated output is imported."""
    run = command_runner or subprocess.run
    try:
        with tempfile.TemporaryDirectory(prefix="ip-studio-imagegen-probe-", dir=temp_root) as raw_dir:
            work_dir = Path(raw_dir).resolve()
            output_path = work_dir / "probe.png"
            events_path = work_dir / "events.jsonl"
            last_message_path = work_dir / "last-message.txt"
            prompt = (
                "Use Codex's native ImageGen image_generation tool to create a simple square "
                "test illustration of a mint-green paper lantern on a plain cream background, "
                "with no text, letters, dialogue, logo, or watermark. Save the generated image "
                f"as PNG at this exact path: {output_path}. Do not draw or synthesize pixels "
                "with code, SVG, shell tools, or another image API. If native ImageGen is "
                "unavailable, report that and do not create a substitute image."
            )
            command = [
                codex_path,
                "exec",
                "--skip-git-repo-check",
                "--ephemeral",
                "--json",
                "--sandbox",
                "workspace-write",
                "-C",
                str(work_dir),
                "--output-last-message",
                str(last_message_path),
                prompt,
            ]
            with events_path.open("w", encoding="utf-8") as events_file:
                result = run(
                    command,
                    cwd=work_dir,
                    stdin=subprocess.DEVNULL,
                    stdout=events_file,
                    stderr=subprocess.DEVNULL,
                    text=True,
                    timeout=timeout_seconds,
                    check=False,
                )
            if result.returncode != 0:
                return ImageGenerationProbeResult(
                    verified=False,
                    reason=f"Codex ImageGen 探测命令失败（退出码 {result.returncode}）。",
                    image=None,
                )
            if not _contains_image_generation_call(events_path):
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="运行记录中没有成功的原生 ImageGen 工具调用。",
                    image=None,
                )
            if output_path.is_symlink() or not output_path.is_file():
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="原生 ImageGen 未在探测目录生成指定 PNG。",
                    image=None,
                )
            if output_path.resolve().parent != work_dir or output_path.stat().st_size > 25 * 1024 * 1024:
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="探测 PNG 路径或大小不符合限制。",
                    image=None,
                )
            image = inspect_image(output_path.read_bytes(), "image/png", 25 * 1024 * 1024, 40_000_000)
            return ImageGenerationProbeResult(
                verified=True,
                reason="原生 ImageGen 工具已生成并解码出有效 PNG。",
                image=image,
            )
    except subprocess.TimeoutExpired:
        return ImageGenerationProbeResult(
            verified=False,
            reason="Codex ImageGen 探测超时。",
            image=None,
        )
    except (OSError, AssetValidationError, ValueError):
        return ImageGenerationProbeResult(
            verified=False,
            reason="Codex ImageGen 探测未产出可解码的受限 PNG。",
            image=None,
        )


def probe_capabilities(
    *,
    executable_lookup: ExecutableLookup | None = None,
    command_runner: CommandRunner | None = None,
    app_server_probe: AppServerProbe | None = None,
    e2e_verified: bool = False,
    verified_codex_path: str | None = None,
    verified_codex_version: str | None = None,
) -> CapabilityReport:
    lookup = executable_lookup or shutil.which
    run = command_runner or subprocess.run
    app_probe = app_server_probe or _read_app_server_capabilities
    checked_at = datetime.now(timezone.utc)
    codex_path = lookup("codex")
    version: str | None = None

    if codex_path is None:
        return CapabilityReport(
            status="unavailable",
            reason="未找到 Codex CLI；在线 ChatGPT 手动生成和导入仍可使用。",
            codex_path=None,
            codex_version=None,
            app_server_available=False,
            image_generation_advertised=False,
            e2e_verified=False,
            checked_at=checked_at,
        )

    version_result = run(
        [codex_path, "--version"], capture_output=True, text=True, timeout=8, check=False
    )
    if version_result.returncode == 0:
        version = (version_result.stdout or "").strip()[:120] or None

    login_result = run(
        [codex_path, "login", "status"], capture_output=True, text=True, timeout=8, check=False
    )
    login_message = f"{login_result.stdout or ''}\n{login_result.stderr or ''}".casefold()
    if login_result.returncode != 0 or "not logged in" in login_message or "logged in" not in login_message:
        return CapabilityReport(
            status="needs_auth",
            reason="Codex CLI 已安装，但当前没有有效登录；请在本机 Codex CLI 完成登录。",
            codex_path=codex_path,
            codex_version=version,
            app_server_available=False,
            image_generation_advertised=False,
            e2e_verified=False,
            checked_at=checked_at,
        )

    try:
        provider_capabilities = app_probe(codex_path)
    except (OSError, RuntimeError, TimeoutError, ValueError, subprocess.SubprocessError):
        return CapabilityReport(
            status="unavailable",
            reason="Codex App Server 无法完成能力协商；保留 ChatGPT Web 人工回退。",
            codex_path=codex_path,
            codex_version=version,
            app_server_available=False,
            image_generation_advertised=False,
            e2e_verified=False,
            checked_at=checked_at,
        )

    image_generation = provider_capabilities.get("imageGeneration") is True
    if not image_generation:
        return CapabilityReport(
            status="unsupported",
            reason="当前 Codex provider 未暴露 ImageGen；保留 ChatGPT Web 人工回退。",
            codex_path=codex_path,
            codex_version=version,
            app_server_available=True,
            image_generation_advertised=False,
            e2e_verified=False,
            checked_at=checked_at,
        )

    e2e_verified = (
        e2e_verified
        and verified_codex_path == codex_path
        and verified_codex_version == version
    )
    if not e2e_verified:
        return CapabilityReport(
            status="unavailable",
            reason="provider 已声明 ImageGen，但本服务尚未验证真实 PNG；请由管理员主动运行生成探测。",
            codex_path=codex_path,
            codex_version=version,
            app_server_available=True,
            image_generation_advertised=True,
            e2e_verified=False,
            checked_at=checked_at,
        )

    return CapabilityReport(
        status="available",
        reason="Codex App Server 已声明 ImageGen，且本服务已验证有效图片输出。",
        codex_path=codex_path,
        codex_version=version,
        app_server_available=True,
        image_generation_advertised=True,
        e2e_verified=True,
        checked_at=checked_at,
    )
