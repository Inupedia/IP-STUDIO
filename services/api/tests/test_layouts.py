from itertools import combinations

import pytest

from app.services.layouts import apply_layout, get_layout, validate_layout


@pytest.mark.parametrize("code, expected_count", [("four", 4), ("six", 6), ("eight", 8)])
def test_four_six_eight_counts_and_panels_do_not_overlap(code: str, expected_count: int) -> None:
    layout = get_layout(code)

    assert len(layout["panels"]) == expected_count
    for first, second in combinations(layout["panels"], 2):
        assert (
            first["x"] + first["width"] <= second["x"]
            or second["x"] + second["width"] <= first["x"]
            or first["y"] + first["height"] <= second["y"]
            or second["y"] + second["height"] <= first["y"]
        )


def test_layout_preserves_brand_version_and_existing_panel_contents() -> None:
    page = {
        "page_id": "page-1",
        "brand_template_version_id": "brand-v1",
        "layout_code": "four",
        "panels": [{"panel_id": f"panel-{index}", "elements": [{"id": f"el-{index}"}]} for index in range(4)],
    }

    updated = apply_layout(page, get_layout("six"))

    assert updated["brand_template_version_id"] == "brand-v1"
    assert updated["layout_code"] == "six"
    assert len(updated["panels"]) == 6
    assert [panel["panel_id"] for panel in updated["panels"][:4]] == [f"panel-{index}" for index in range(4)]
    assert updated["panels"][0]["elements"] == [{"id": "el-0"}]
    assert updated["panels"][3]["elements"] == [{"id": "el-3"}]
    assert updated["panels"][4]["elements"] == []


def test_custom_layout_schema_rejects_overlap_and_out_of_bounds_geometry() -> None:
    with pytest.raises(ValueError, match="overlap"):
        validate_layout({
            "code": "custom",
            "width": 500,
            "height": 500,
            "margin": 0,
            "gap": 0,
            "panels": [
                {"panel_id": "a", "x": 10, "y": 10, "width": 200, "height": 200},
                {"panel_id": "b", "x": 100, "y": 100, "width": 200, "height": 200},
            ],
        })
    with pytest.raises(ValueError, match="outside the page"):
        validate_layout({
            "code": "custom",
            "width": 500,
            "height": 500,
            "margin": 0,
            "gap": 0,
            "panels": [{"panel_id": "a", "x": 400, "y": 10, "width": 200, "height": 200}],
        })


def test_apply_layout_refuses_to_discard_content_in_removed_panels() -> None:
    page = {
        "brand_template_version_id": "brand-v1",
        "panels": [
            {"panel_id": f"panel-{index}", "elements": ([{"id": "content"}] if index == 7 else [])}
            for index in range(8)
        ],
    }

    with pytest.raises(ValueError, match="discard panel elements"):
        apply_layout(page, get_layout("four"))
