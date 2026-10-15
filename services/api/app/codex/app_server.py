"""Read native ImageGen evidence from Codex's public local App Server protocol."""

from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from app.codex.image_result import ImageResultError, ValidatedImage, validate_image_result

MAX_EVENT_LOG_BYTES = 16 * 1024 * 1024
MAX_APP_SERVER_RESPONSE_BYTES = 64 * 1024 * 1024


@dataclass(frozen=True)
class ImageGenerationHistoryItem:
    status: str
    saved_path: str | None


def thread_id_from_jsonl(events_path: Path) -> str | None:
    """Return the thread ID from Codex's own JSONL startup event."""
    try:
        if not events_path.is_file() or events_path.stat().st_size > MAX_EVENT_LOG_BYTES:
            return None
        with events_path.open(encoding="utf-8") as events_file:
            for line in events_file:
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if not isinstance(event, dict) or event.get("type") not in {
                    "thread.started", "thread_started",
                }:
                    continue
                thread = event.get("thread")
                thread_id = event.get("thread_id") or event.get("threadId")
                if not isinstance(thread_id, str) and isinstance(thread, dict):
                    thread_id = thread.get("id")
                if isinstance(thread_id, str):
                    try:
                        return str(UUID(thread_id))
                    except ValueError:
                        return None
    except OSError:
        return None
    return None


def _thread_image_generation_items(result: object) -> list[ImageGenerationHistoryItem]:
    if not isinstance(result, dict):
        raise RuntimeError("Codex App Server returned an invalid thread response")
    thread = result.get("thread")
    turns = thread.get("turns") if isinstance(thread, dict) else None
    if not isinstance(turns, list):
        raise RuntimeError("Codex App Server thread history is unavailable")

    items: list[ImageGenerationHistoryItem] = []
    for turn in turns:
        turn_items = turn.get("items") if isinstance(turn, dict) else None
        if not isinstance(turn_items, list):
            continue
        for item in turn_items:
            if not isinstance(item, dict) or item.get("type") != "imageGeneration":
                continue
            status = item.get("status")
            saved_path = item.get("savedPath") or item.get("saved_path")
            items.append(ImageGenerationHistoryItem(
                status=status if isinstance(status, str) else "",
                saved_path=saved_path if isinstance(saved_path, str) else None,
            ))
            if len(items) >= 32:
                return items
    return items


def read_thread_image_generation_items(
    codex_path: str,
    thread_id: str,
    *,
    timeout_seconds: float = 30.0,
    delete_thread_after_read: bool = False,
) -> list[ImageGenerationHistoryItem]:
    """Read persisted native ImageGen items without logging their image payloads."""
    try:
        normalized_thread_id = str(UUID(thread_id))
    except ValueError as error:
        raise RuntimeError("Codex returned an invalid thread ID") from error

    process = subprocess.Popen(
        [codex_path, "app-server", "--listen", "stdio://"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    messages: queue.Queue[dict[str, object] | None] = queue.Queue()
    response_size: list[int] = [0]

    def collect_stdout() -> None:
        assert process.stdout is not None
        while True:
            remaining_bytes = MAX_APP_SERVER_RESPONSE_BYTES - response_size[0]
            line = process.stdout.readline(remaining_bytes + 1)
            if not line:
                break
            response_size[0] += len(line)
            if response_size[0] > MAX_APP_SERVER_RESPONSE_BYTES:
                messages.put({"_localError": "response_too_large"})
                break
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(message, dict):
                messages.put(message)
        messages.put(None)

    def drain_stderr(stream: BinaryIO | None) -> None:
        if stream is None:
            return
        for _line in stream:
            pass

    stdout_reader = threading.Thread(target=collect_stdout, daemon=True)
    stderr_reader = threading.Thread(target=drain_stderr, args=(process.stderr,), daemon=True)
    stdout_reader.start()
    stderr_reader.start()

    def send(payload: dict[str, object]) -> None:
        if process.stdin is None:
            raise RuntimeError("Codex App Server input is unavailable")
        process.stdin.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))
        process.stdin.flush()

    def response_for(request_id: int, timeout: float = timeout_seconds) -> dict[str, object]:
        try:
            while True:
                message = messages.get(timeout=timeout)
                if message is None:
                    raise RuntimeError("Codex App Server closed before replying")
                if message.get("_localError") == "response_too_large":
                    raise RuntimeError("Codex App Server thread history exceeded its size limit")
                if message.get("id") != request_id:
                    continue
                if "error" in message:
                    raise RuntimeError("Codex App Server thread history request failed")
                result = message.get("result")
                if not isinstance(result, dict):
                    raise RuntimeError("Codex App Server returned an invalid response")
                return result
        except queue.Empty as error:
            raise TimeoutError("Codex App Server thread history request timed out") from error

    read_error: BaseException | None = None
    try:
        send({
            "id": 1,
            "method": "initialize",
            "params": {"clientInfo": {"name": "ip-studio", "version": "0.1.0"}},
        })
        response_for(1)
        send({"method": "initialized"})
        send({
            "id": 2,
            "method": "thread/read",
            "params": {"threadId": normalized_thread_id, "includeTurns": True},
        })
        result = response_for(2)
        return _thread_image_generation_items(result)
    except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError) as error:
        read_error = error
        raise
    finally:
        if delete_thread_after_read and process.poll() is None:
            try:
                send({
                    "id": 3,
                    "method": "thread/delete",
                    "params": {"threadId": normalized_thread_id},
                })
                response_for(3, timeout=5.0)
            except (OSError, RuntimeError, TimeoutError, subprocess.SubprocessError):
                pass
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        if read_error is None:
            stdout_reader.join(timeout=1)
            stderr_reader.join(timeout=1)


def _safe_generated_image_path(saved_path: str, thread_id: str) -> Path | None:
    try:
        normalized_thread_id = str(UUID(thread_id))
        codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")).expanduser()
        generated_root = (codex_home / "generated_images").resolve()
        expected_thread_dir = (generated_root / normalized_thread_id).resolve()
        candidate = Path(saved_path).expanduser()
        if not candidate.is_absolute() or candidate.is_symlink():
            return None
        resolved = candidate.resolve(strict=True)
        if (
            not expected_thread_dir.is_relative_to(generated_root)
            or resolved.parent != expected_thread_dir
            or resolved.suffix.casefold() != ".png"
            or not resolved.is_file()
        ):
            return None
        return resolved
    except (OSError, RuntimeError, ValueError):
        return None


def cleanup_generated_image_files(
    items: list[ImageGenerationHistoryItem],
    thread_id: str,
    *,
    preserve: Path | None = None,
) -> None:
    """Remove only direct PNG outputs under the generated thread's Codex-owned folder."""
    preserved = preserve.resolve() if preserve is not None else None
    for item in items:
        if not item.saved_path:
            continue
        path = _safe_generated_image_path(item.saved_path, thread_id)
        if path is None or path == preserved:
            continue
        try:
            path.unlink(missing_ok=True)
            path.parent.rmdir()
        except OSError:
            pass


def validate_native_image_generation_output(
    items: list[ImageGenerationHistoryItem],
    thread_id: str,
    output_path: Path,
    allowed_dir: Path,
) -> ValidatedImage:
    """Require a completed native item whose saved PNG exactly matches bounded output."""
    completed_items = [item for item in items if item.status.casefold() == "completed"]
    if not completed_items:
        raise ImageResultError("Codex run did not record a completed native ImageGen call")

    generated = validate_image_result(output_path, allowed_dir)
    if generated.image.mime != "image/png":
        raise ImageResultError("Codex ImageGen output must be a PNG")

    matched_saved_path: Path | None = None
    for item in completed_items:
        if not item.saved_path:
            continue
        saved_path = _safe_generated_image_path(item.saved_path, thread_id)
        if saved_path is None:
            continue
        try:
            native_image = validate_image_result(saved_path, saved_path.parent)
            if (
                native_image.image.mime == "image/png"
                and saved_path.read_bytes() == generated.path.read_bytes()
            ):
                matched_saved_path = saved_path
                break
        except (ImageResultError, OSError):
            continue
    if matched_saved_path is None:
        raise ImageResultError("Codex output did not match a completed native ImageGen PNG")
    return generated
