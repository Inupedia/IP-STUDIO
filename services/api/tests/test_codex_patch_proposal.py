from copy import deepcopy
import json
from pathlib import Path
import subprocess
from uuid import UUID

import pytest

from app.services.codex_patch_proposal import PatchProposalUnavailable, propose_patch
from app.services.patch_validator import Scope


def test_proposal_uses_read_only_local_cli_and_binds_server_scope(tmp_path, monkeypatch) -> None:
    document = {
        "schema_version": "1.0",
        "episode_id": "10000000-0000-4000-8000-000000000003",
        "revision": 4,
        "style_version_id": None,
        "brand_template_version_id": "10000000-0000-4000-8000-000000000004",
        "dynamic_fields": {"title": "测试", "episode_number": "EP.01"},
        "pages": [{
            "id": "10000000-0000-4000-8000-000000000005",
            "width": 1080,
            "height": 1440,
            "order": 1,
            "layout_code": "custom",
            "brand_template_version_id": "10000000-0000-4000-8000-000000000004",
            "panels": [{
                "id": "10000000-0000-4000-8000-000000000006",
                "rect": {"x": 0, "y": 0, "width": 1080, "height": 1440},
                "elements": [],
            }],
        }],
    }
    scope = Scope(
        workspace_id=UUID("10000000-0000-4000-8000-000000000001"),
        ip_id=UUID("10000000-0000-4000-8000-000000000002"),
        episode_id=UUID(document["episode_id"]),
        document_id=UUID("10000000-0000-4000-8000-000000000007"),
        document=deepcopy(document),
        authorized_asset_version_ids=frozenset(),
    )
    observed: dict[str, object] = {}
    monkeypatch.setattr("app.services.codex_patch_proposal.shutil.which", lambda _name: "/opt/codex")

    def run(command, **kwargs):
        observed["command"] = command
        observed["kwargs"] = kwargs
        output = Path(command[command.index("--output-last-message") + 1])
        output.write_text(json.dumps({
            "summary": "更新文本",
            "operations": [{
                "op": "set_text",
                "element_id": "10000000-0000-4000-8000-000000000008",
                "text": "已更新",
            }],
        }, ensure_ascii=False), encoding="utf-8")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr("app.services.codex_patch_proposal.subprocess.run", run)
    proposal = propose_patch(
        instruction="改一下文字",
        document=document,
        scope=scope,
        base_revision=4,
    )

    command = observed["command"]
    assert proposal.workspace_id == scope.workspace_id
    assert proposal.ip_id == scope.ip_id
    assert proposal.document_id == scope.document_id
    assert proposal.base_revision == 4
    assert proposal.operations[0].op == "set_text"
    assert command[command.index("--sandbox") + 1] == "read-only"
    assert "--ignore-user-config" in command
    assert observed["kwargs"]["stdin"] is subprocess.DEVNULL
    assert "shell" not in observed["kwargs"]


def test_missing_local_cli_uses_manual_edit_fallback(monkeypatch) -> None:
    monkeypatch.setattr("app.services.codex_patch_proposal.shutil.which", lambda _name: None)

    with pytest.raises(PatchProposalUnavailable, match="手动编辑"):
        propose_patch(
            instruction="改字",
            document={},
            scope=Scope(
                workspace_id=UUID("10000000-0000-4000-8000-000000000001"),
                ip_id=UUID("10000000-0000-4000-8000-000000000002"),
                episode_id=UUID("10000000-0000-4000-8000-000000000003"),
                document_id=UUID("10000000-0000-4000-8000-000000000004"),
                document={},
                authorized_asset_version_ids=frozenset(),
            ),
            base_revision=1,
        )
