from itertools import combinations
from typing import Literal

LayoutCode = Literal["four", "six", "eight"]

_ROW_COUNTS: dict[LayoutCode, int] = {"four": 2, "six": 3, "eight": 4}


def get_layout(
    code: LayoutCode, width: int = 1080, height: int = 1440, margin: int = 48, gap: int = 24
) -> dict[str, object]:
    if width <= margin * 2 or height <= margin * 2 or gap < 0:
        raise ValueError("Page size must leave room for layout margins")
    rows = _ROW_COUNTS[code]
    columns = 2
    panel_width = (width - margin * 2 - gap * (columns - 1)) / columns
    panel_height = (height - margin * 2 - gap * (rows - 1)) / rows
    if panel_width <= 0 or panel_height <= 0:
        raise ValueError("Page size is too small for the requested layout")
    panels = [
        {
            "panel_id": f"panel-{index + 1:02d}",
            "x": margin + column * (panel_width + gap),
            "y": margin + row * (panel_height + gap),
            "width": panel_width,
            "height": panel_height,
        }
        for index, (row, column) in enumerate(
            (row, column) for row in range(rows) for column in range(columns)
        )
    ]
    layout = {
        "code": code,
        "width": width,
        "height": height,
        "margin": margin,
        "gap": gap,
        "panels": panels,
    }
    validate_layout(layout)
    return layout


def validate_layout(layout: dict[str, object]) -> None:
    width = float(layout["width"])
    height = float(layout["height"])
    panels = layout["panels"]
    if not isinstance(panels, list) or not panels:
        raise ValueError("A page layout must contain at least one panel")
    ids: set[str] = set()
    for panel in panels:
        if not isinstance(panel, dict):
            raise ValueError("Panel geometry must be an object")
        panel_id = str(panel.get("panel_id", ""))
        x, y, panel_width, panel_height = (
            float(panel[key]) for key in ("x", "y", "width", "height")
        )
        if not panel_id or panel_id in ids:
            raise ValueError("Panel ids must be non-empty and unique")
        ids.add(panel_id)
        if x < 0 or y < 0 or panel_width <= 0 or panel_height <= 0:
            raise ValueError("Panel geometry must use non-negative positions and positive dimensions")
        if x + panel_width > width or y + panel_height > height:
            raise ValueError(f"Panel {panel_id} falls outside the page")
    for first, second in combinations(panels, 2):
        first_right = float(first["x"]) + float(first["width"])
        second_right = float(second["x"]) + float(second["width"])
        first_bottom = float(first["y"]) + float(first["height"])
        second_bottom = float(second["y"]) + float(second["height"])
        if not (
            first_right <= float(second["x"])
            or second_right <= float(first["x"])
            or first_bottom <= float(second["y"])
            or second_bottom <= float(first["y"])
        ):
            raise ValueError(f"Panels {first['panel_id']} and {second['panel_id']} overlap")


def apply_layout(page: dict[str, object], layout: dict[str, object]) -> dict[str, object]:
    validate_layout(layout)
    previous_panels = page.get("panels", [])
    new_geometry = layout["panels"]
    if not isinstance(previous_panels, list) or not isinstance(new_geometry, list):
        raise ValueError("Page panels and layout geometry must be lists")
    if len(previous_panels) > len(new_geometry) and any(
        isinstance(panel, dict) and panel.get("elements") for panel in previous_panels[len(new_geometry):]
    ):
        raise ValueError("Changing this layout would discard panel elements")
    panels: list[dict[str, object]] = []
    for index, geometry in enumerate(new_geometry):
        old = previous_panels[index] if index < len(previous_panels) and isinstance(previous_panels[index], dict) else {}
        panels.append({
            **old,
            **geometry,
            "elements": old.get("elements", []),
        })
    updated = {
        **page,
        "layout_code": layout["code"],
        "width": layout["width"],
        "height": layout["height"],
        "panels": panels,
    }
    return updated
