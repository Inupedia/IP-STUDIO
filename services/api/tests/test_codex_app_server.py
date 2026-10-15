import json
from io import BytesIO, StringIO
from pathlib import Path

import pytest

from app.codex.app_server import (
    ImageGenerationHistoryItem,
    read_thread_image_generation_items,
    thread_id_from_jsonl,
)


THREAD_ID = "018f2f70-6af7-7a4b-b1d1-0d21db2db931"


def test_thread_id_is_read_only_from_codex_thread_started_event(tmp_path: Path) -> None:
    events = tmp_path / "events.jsonl"
    events.write_text(
        json.dumps({"type": "agent_message", "text": THREAD_ID}) + "\n"
        + json.dumps({"type": "thread.started", "thread_id": THREAD_ID}) + "\n",
        encoding="utf-8",
    )

    assert thread_id_from_jsonl(events) == THREAD_ID


def test_thread_id_rejects_invalid_ids_and_oversized_logs(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.jsonl"
    invalid.write_text(json.dumps({"type": "thread.started", "thread_id": "../outside"}), encoding="utf-8")
    oversized = tmp_path / "oversized.jsonl"
    oversized.write_bytes(b" " * (16 * 1024 * 1024 + 1))

    assert thread_id_from_jsonl(invalid) is None
    assert thread_id_from_jsonl(oversized) is None


def test_app_server_reads_only_item_metadata_then_deletes_probe_thread(monkeypatch) -> None:
    image_item = {
        "type": "imageGeneration",
        "status": "completed",
        "savedPath": "/tmp/codex/generated_images/example.png",
        "result": "very-large-base64-image-payload",
    }
    server_output = "\n".join([
        json.dumps({"id": 1, "result": {"serverInfo": {"name": "codex"}}}),
        json.dumps({"id": 2, "result": {"thread": {"turns": [{"items": [image_item]}]}}}),
        json.dumps({"id": 3, "result": {}}),
    ]) + "\n"
    observed: dict[str, object] = {}
    requests: list[dict[str, object]] = []

    class FakeStdin:
        def write(self, line: str) -> int:
            requests.append(json.loads(line))
            return len(line)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeProcess:
        def __init__(self, command, **_kwargs):
            observed["command"] = command
            self.stdin = FakeStdin()
            self.stdout = BytesIO(server_output.encode("utf-8"))
            self.stderr = BytesIO()
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            self.returncode = self.returncode or 0
            return self.returncode

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr("app.codex.app_server.subprocess.Popen", FakeProcess)

    items = read_thread_image_generation_items(
        "/opt/codex",
        THREAD_ID,
        delete_thread_after_read=True,
    )

    assert items == [ImageGenerationHistoryItem(status="completed", saved_path=image_item["savedPath"])]
    assert items[0].__dict__.keys() == {"status", "saved_path"}
    assert [request.get("method") for request in requests] == [
        "initialize",
        "initialized",
        "thread/read",
        "thread/delete",
    ]
    assert requests[2]["params"] == {"threadId": THREAD_ID, "includeTurns": True}


def test_app_server_bounds_each_stdout_read_before_buffering_history(monkeypatch) -> None:
    class TrackingStdout:
        def __init__(self, payload: str):
            self.stream = StringIO(payload)
            self.read_sizes: list[int] = []

        def readline(self, size: int = -1) -> str:
            self.read_sizes.append(size)
            return self.stream.readline(size)

        def __iter__(self):
            return self

        def __next__(self) -> str:
            line = self.readline()
            if not line:
                raise StopIteration
            return line

    initialize = json.dumps({"id": 1, "result": {}}) + "\n"
    oversized = '{"payload":"' + "x" * 1024 + '"}\n'
    stdout = TrackingStdout(initialize + oversized)
    requests: list[dict[str, object]] = []

    class FakeStdin:
        def write(self, line: bytes) -> int:
            requests.append(json.loads(line))
            return len(line)

        def flush(self) -> None:
            return None

        def close(self) -> None:
            return None

    class FakeProcess:
        def __init__(self, _command, **_kwargs):
            self.stdin = FakeStdin()
            self.stdout = stdout
            self.stderr = BytesIO()
            self.returncode = None

        def poll(self):
            return self.returncode

        def terminate(self):
            self.returncode = -15

        def wait(self, timeout=None):
            self.returncode = self.returncode or 0
            return self.returncode

        def kill(self):
            self.returncode = -9

    monkeypatch.setattr("app.codex.app_server.subprocess.Popen", FakeProcess)
    monkeypatch.setattr("app.codex.app_server.MAX_APP_SERVER_RESPONSE_BYTES", 128)

    with pytest.raises(RuntimeError, match="exceeded its size limit"):
        read_thread_image_generation_items("/opt/codex", THREAD_ID)

    assert stdout.read_sizes
    assert all(0 <= size <= 129 for size in stdout.read_sizes)
