"""Bounded adapter for the authenticated local Codex CLI."""

from __future__ import annotations

import hashlib
import json
import os
import signal
import subprocess
from threading import RLock
from pathlib import Path
from zipfile import BadZipFile, ZipFile

from app.codex.app_server import (
    ImageGenerationHistoryItem,
    cleanup_generated_image_directory,
    cleanup_generated_image_files,
    read_thread_image_generation_items,
    thread_id_from_jsonl,
    validate_native_image_generation_output,
)
from app.codex.image_result import ImageResultError, ValidatedImage, validate_image_result

MAX_REFERENCE_FILES = 100
MAX_REFERENCE_BYTES = 100 * 1024 * 1024
_process_lock = RLock()
_processes: dict[str, subprocess.Popen[bytes]] = {}
_cancellation_requests: set[str] = set()


def _terminate_process_tree(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        try:
            process.terminate()
        except OSError:
            return
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            try:
                process.kill()
            except OSError:
                return
        process.wait(timeout=3)


class CodexRunCancelled(ImageResultError):
    pass


def request_codex_cancellation(run_id: str) -> None:
    with _process_lock:
        _cancellation_requests.add(run_id)
        process = _processes.get(run_id)
    if process is not None:
        _terminate_process_tree(process)


def clear_codex_cancellation(run_id: str) -> None:
    with _process_lock:
        _cancellation_requests.discard(run_id)
        _processes.pop(run_id, None)


def _run_key(job_dir: Path) -> str | None:
    prefix = "run-"
    candidate = job_dir.name[len(prefix):len(prefix) + 36] if job_dir.name.startswith(prefix) else ""
    if len(candidate) != 36:
        return None
    try:
        from uuid import UUID

        return str(UUID(candidate))
    except ValueError:
        return None


def _safe_member_path(root: Path, name: str) -> Path:
    candidate_name = Path(name)
    if candidate_name.is_absolute() or ".." in candidate_name.parts:
        raise ImageResultError("Reference bundle contains an unsafe path")
    destination = (root / candidate_name).resolve()
    if not destination.is_relative_to(root.resolve()):
        raise ImageResultError("Reference bundle path escapes the job directory")
    return destination


def _extract_frozen_references(bundle: bytes, task_id: str, destination: Path) -> list[Path]:
    try:
        from io import BytesIO

        with ZipFile(BytesIO(bundle)) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_REFERENCE_FILES + 2:
                raise ImageResultError("Reference bundle has too many entries")
            if sum(info.file_size for info in infos) > MAX_REFERENCE_BYTES:
                raise ImageResultError("Reference bundle exceeds its size limit")
            if any(info.flag_bits & 1 for info in infos):
                raise ImageResultError("Encrypted reference bundles are not accepted")
            names = {info.filename for info in infos}
            if "manifest.json" not in names:
                raise ImageResultError("Reference bundle has no manifest")
            manifest = json.loads(archive.read("manifest.json"))
            if not isinstance(manifest, dict) or manifest.get("task_id") != task_id:
                raise ImageResultError("Reference bundle does not belong to this task")
            assets = manifest.get("assets")
            if not isinstance(assets, list) or len(assets) > MAX_REFERENCE_FILES:
                raise ImageResultError("Reference bundle manifest is invalid")

            files: list[Path] = []
            seen: set[str] = set()
            for asset in assets:
                if not isinstance(asset, dict):
                    raise ImageResultError("Reference bundle manifest is invalid")
                member_name = asset.get("path")
                sha256 = asset.get("sha256")
                if not isinstance(member_name, str) or not isinstance(sha256, str):
                    raise ImageResultError("Reference bundle manifest is invalid")
                if member_name in seen or member_name not in names:
                    raise ImageResultError("Reference bundle is missing a declared image")
                seen.add(member_name)
                member_path = _safe_member_path(destination, member_name)
                content = archive.read(member_name)
                if hashlib.sha256(content).hexdigest() != sha256:
                    raise ImageResultError("A frozen reference failed its SHA-256 check")
                member_path.parent.mkdir(parents=True, exist_ok=True)
                member_path.write_bytes(content)
                files.append(member_path)
            return files
    except (BadZipFile, KeyError, OSError, json.JSONDecodeError) as error:
        raise ImageResultError("Reference bundle could not be validated") from error


def generate_image(
    codex_path: str,
    prompt: str,
    bundle: bytes,
    job_dir: Path,
    *,
    timeout_seconds: int = 300,
) -> ValidatedImage:
    """Generate one bitmap using `codex exec`; never invokes a private API."""
    job_dir.mkdir(parents=True, exist_ok=True)
    root = job_dir.resolve(strict=True)
    references_dir = root / "references"
    references_dir.mkdir(mode=0o700)
    reference_paths = _extract_frozen_references(bundle, str(_manifest_task_id(bundle)), references_dir)
    output_path = root / "result.png"
    events_path = root / "events.jsonl"
    codex_prompt = (
        "Use only Codex's native ImageGen image_generation tool to create the requested comic panel. "
        "Follow this task prompt: \n\n"
        f"{prompt}\n\n"
        "Do not draw or fabricate pixels with code, SVG, shell, another image API, or a browser. "
        "Create one image only, save it as PNG to the exact path supplied below, and do not include "
        "letters, words, dialogue, logos, captions, UI, or watermarks in the bitmap. All text is "
        "rendered separately by IP Studio. If native ImageGen is unavailable, report failure and "
        "do not create a substitute. Output path: "
        f"{output_path}"
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
        str(root),
    ]
    for reference in reference_paths:
        command.extend(["-i", str(reference)])
    command.append(codex_prompt)

    run_key = _run_key(root)
    if run_key is not None:
        with _process_lock:
            if run_key in _cancellation_requests:
                _cancellation_requests.discard(run_key)
                raise CodexRunCancelled("Codex run was canceled")
    process: subprocess.Popen[bytes] | None = None
    thread_id: str | None = None
    image_items: list[ImageGenerationHistoryItem] = []
    timed_out = False
    try:
        with events_path.open("w", encoding="utf-8") as event_file:
            process = subprocess.Popen(
                command,
                cwd=root,
                stdin=subprocess.DEVNULL,
                stdout=event_file,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            if run_key is not None:
                with _process_lock:
                    if run_key in _cancellation_requests:
                        _terminate_process_tree(process)
                    else:
                        _processes[run_key] = process
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                _terminate_process_tree(process)
                return_code = process.returncode
            finally:
                if run_key is not None:
                    with _process_lock:
                        _processes.pop(run_key, None)
                        was_cancelled = run_key in _cancellation_requests
                        _cancellation_requests.discard(run_key)
                else:
                    was_cancelled = False
    except OSError as error:
        raise ImageResultError("Codex CLI could not be started") from error
    thread_id = thread_id_from_jsonl(events_path)
    try:
        if thread_id is not None:
            try:
                image_items = read_thread_image_generation_items(
                    codex_path,
                    thread_id,
                    timeout_seconds=30.0,
                    delete_thread_after_read=True,
                )
            except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
                if timed_out:
                    raise ImageResultError("Codex ImageGen timed out") from error
                if was_cancelled:
                    raise CodexRunCancelled("Codex run was canceled") from error
                raise ImageResultError("Codex App Server could not read the native ImageGen result") from error
        if was_cancelled:
            raise CodexRunCancelled("Codex run was canceled")
        if timed_out:
            raise ImageResultError("Codex ImageGen timed out")
        if return_code != 0:
            raise ImageResultError(f"Codex ImageGen failed with exit code {return_code}")
        if thread_id is None:
            raise ImageResultError("Codex run did not produce a persistent session ID")
        if not image_items:
            raise ImageResultError("Codex run did not record a successful native ImageGen call")
        try:
            return validate_native_image_generation_output(image_items, thread_id, output_path, root)
        except ImageResultError as error:
            raise ImageResultError("Codex run did not produce a matching native ImageGen PNG") from error
    finally:
        if thread_id is not None:
            cleanup_generated_image_files(image_items, thread_id)
            cleanup_generated_image_directory(thread_id)


def _manifest_task_id(bundle: bytes) -> str:
    """Read task ID for adapter validation; full schema is checked during extraction."""
    from io import BytesIO

    try:
        with ZipFile(BytesIO(bundle)) as archive:
            manifest = json.loads(archive.read("manifest.json"))
    except (BadZipFile, KeyError, json.JSONDecodeError) as error:
        raise ImageResultError("Reference bundle could not be validated") from error
    task_id = manifest.get("task_id") if isinstance(manifest, dict) else None
    if not isinstance(task_id, str):
        raise ImageResultError("Reference bundle manifest is invalid")
    return task_id
