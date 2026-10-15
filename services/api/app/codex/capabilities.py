"""Inspect the local Codex runtime without spending image-generation usage."""

from __future__ import annotations

import json
import os
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

from app.codex.app_server import (
    ImageGenerationHistoryItem,
    cleanup_generated_image_directory,
    cleanup_generated_image_files,
    read_thread_image_generation_items,
    thread_id_from_jsonl,
    validate_native_image_generation_output,
)
from app.codex.image_result import ImageResultError
from app.storage.local_blobs import AssetValidationError, ImageInfo

CapabilityStatus = Literal["available", "unavailable", "needs_auth", "unsupported"]
CommandRunner = Callable[..., subprocess.CompletedProcess[str]]
ExecutableLookup = Callable[[str], str | None]
AppServerProbe = Callable[[str], dict[str, object]]
ThreadImageGenerationReader = Callable[[str, str], list[ImageGenerationHistoryItem]]


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


def run_image_generation_probe(
    codex_path: str,
    *,
    temp_root: Path | None = None,
    command_runner: CommandRunner | None = None,
    thread_image_generation_reader: ThreadImageGenerationReader | None = None,
    timeout_seconds: int = 240,
) -> ImageGenerationProbeResult:
    """Run only after an explicit administrator action; no generated output is imported."""
    run = command_runner or subprocess.run
    read_thread_items = thread_image_generation_reader or (
        lambda path, thread_id: read_thread_image_generation_items(
            path,
            thread_id,
            timeout_seconds=min(30.0, max(5.0, float(timeout_seconds))),
            delete_thread_after_read=True,
        )
    )
    try:
        with tempfile.TemporaryDirectory(prefix="ip-studio-imagegen-probe-", dir=temp_root) as raw_dir:
            work_dir = Path(raw_dir).resolve()
            output_path = work_dir / "probe.png"
            events_path = work_dir / "events.jsonl"
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
                "--json",
                "--enable",
                "image_generation",
                "--sandbox",
                "workspace-write",
                "-C",
                str(work_dir),
                prompt,
            ]
            timed_out = False
            result: subprocess.CompletedProcess[str] | None = None
            try:
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
            except subprocess.TimeoutExpired:
                timed_out = True
            thread_id = thread_id_from_jsonl(events_path)
            if timed_out:
                if thread_id is not None:
                    try:
                        items = read_thread_items(codex_path, thread_id)
                        cleanup_generated_image_files(items, thread_id)
                    except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError):
                        pass
                    cleanup_generated_image_directory(thread_id)
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="Codex ImageGen 探测超时。",
                    image=None,
                )
            if result is None:
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="Codex ImageGen 探测未返回命令结果。",
                    image=None,
                )
            if result.returncode != 0:
                if thread_id is not None:
                    try:
                        items = read_thread_items(codex_path, thread_id)
                        cleanup_generated_image_files(items, thread_id)
                    except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError):
                        pass
                    cleanup_generated_image_directory(thread_id)
                return ImageGenerationProbeResult(
                    verified=False,
                    reason=f"Codex ImageGen 探测命令失败（退出码 {result.returncode}）。",
                    image=None,
                )
            if thread_id is None:
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="Codex 运行记录中没有可回读的持久化 session。",
                    image=None,
                )
            try:
                items = read_thread_items(codex_path, thread_id)
            except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError):
                cleanup_generated_image_directory(thread_id)
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="Codex App Server 未能回读本次运行的原生 ImageGen 记录。",
                    image=None,
                )
            try:
                generated = validate_native_image_generation_output(items, thread_id, output_path, work_dir)
                return ImageGenerationProbeResult(
                    verified=True,
                    reason="Codex App Server 已确认原生 ImageGen，且同一结果通过 PNG 完整解码。",
                    image=generated.image,
                )
            except ImageResultError as error:
                reason = (
                    "运行记录中没有成功的原生 ImageGen 工具调用。"
                    if "did not record a completed native ImageGen" in str(error)
                    else "原生 ImageGen 记录与受限 PNG 未能匹配验证。"
                )
                return ImageGenerationProbeResult(
                    verified=False,
                    reason=reason,
                    image=None,
                )
            except (AssetValidationError, OSError, ValueError, RuntimeError):
                return ImageGenerationProbeResult(
                    verified=False,
                    reason="原生 ImageGen 记录与受限 PNG 未能匹配验证。",
                    image=None,
                )
            finally:
                cleanup_generated_image_files(items, thread_id)
                cleanup_generated_image_directory(thread_id)
    except (ImageResultError, OSError, AssetValidationError, ValueError, RuntimeError, TimeoutError):
        return ImageGenerationProbeResult(
            verified=False,
            reason="Codex ImageGen 探测未产出可解码的受限 PNG。",
            image=None,
        )


def probe_capabilities(
    *,
    configured_codex_path: Path | str | None = None,
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
    if configured_codex_path is not None:
        configured_path = Path(configured_codex_path).expanduser()
        if (
            not configured_path.is_absolute()
            or not configured_path.is_file()
            or not os.access(configured_path, os.X_OK)
        ):
            return CapabilityReport(
                status="unavailable",
                reason="配置的 Codex ImageGen 可执行文件不可用；请检查绝对路径和执行权限。",
                codex_path=None,
                codex_version=None,
                app_server_available=False,
                image_generation_advertised=False,
                e2e_verified=False,
                checked_at=checked_at,
            )
        codex_path = str(configured_path.resolve())
    else:
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
