import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.schemas.canvas import CanvasDocument, resolve_message_side

FIXTURE = Path(__file__).parents[3] / "packages" / "contracts" / "fixtures" / "canvas-v1.json"


def test_canvas_fixture_matches_python_schema_and_uses_snake_case_fields() -> None:
    canvas = CanvasDocument.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))

    assert canvas.schema_version == "1.0"
    assert canvas.brand_template_version_id
    assert canvas.pages[0].brand_template_version_id == canvas.brand_template_version_id


def test_canvas_requires_brand_version_and_valid_asset_version_uuid() -> None:
    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    del document["brand_template_version_id"]
    with pytest.raises(ValidationError):
        CanvasDocument.model_validate(document)

    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document["pages"][0]["panels"][0]["elements"][0]["asset_version_id"] = "broken-asset-id"
    with pytest.raises(ValidationError):
        CanvasDocument.model_validate(document)


def test_ep01_chat_direction_matches_product_acceptance() -> None:
    assert resolve_message_side("friend-id", "kazi-id") == "left"
    assert resolve_message_side("kazi-id", "kazi-id") == "right"
