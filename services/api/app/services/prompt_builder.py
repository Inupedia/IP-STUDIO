from typing import Any


def build_prompt(panel: dict[str, Any], references: list[dict[str, Any]]) -> dict[str, Any]:
    """Build a copyable, lettering-free prompt from a panel and frozen refs."""
    character_refs = [
        reference for reference in references if reference["kind"] == "character_version"
    ]
    style_refs = [reference for reference in references if reference["kind"] == "style_version"]

    lines = [
        "为 IP Studio 生成一张独立漫画单格插画。",
        "必须是单格构图，只生成画面素材，不生成整页或品牌外壳。",
    ]
    if character_refs:
        lines.append(
            "严格遵循已批准角色版本（使用精确版本，禁止自行改造）："
        )
        lines.extend(
            f"- {reference['name']}，CharacterVersion {reference['version_no']}，"
            f"ID {reference['version_id']}："
            f"{reference['bible_summary']}"
            for reference in character_refs
        )
    if style_refs:
        lines.append("严格遵循以下已批准画风版本：")
        lines.extend(
            f"- {reference['name']}，StyleVersion {reference['version_no']}，"
            f"ID {reference['version_id']}："
            f"{reference['bible_summary']}"
            for reference in style_refs
        )

    lines.extend([
        (
            f"场景：{panel['scene_name']}；地点：{panel['location']}；"
            f"时间：{panel['time']}。"
        ),
        f"镜头：{panel['shot_type']}。",
        f"画面动作：{panel['action']}",
        f"无字画面要求：{panel['no_text_prompt']}",
        (
            "图像中不得出现文字、字母、数字、对话、字幕、聊天消息、"
            "气泡、页码、Logo 或水印。"
        ),
        (
            "所有中文、对话、聊天消息和气泡将由 IP Studio 后续作为"
            "独立原生对象绘制。"
        ),
        f"冻结版本 ID：{', '.join(reference['version_id'] for reference in references)}",
    ])
    return {
        "schema_version": "1.0",
        "text": "\n".join(lines),
        "panel": {
            "panel_id": str(panel["panel_id"]),
            "panel_order": panel["panel_order"],
            "scene_name": panel["scene_name"],
            "location": panel["location"],
            "time": panel["time"],
            "action": panel["action"],
            "shot_type": panel["shot_type"],
            "no_text_prompt": panel["no_text_prompt"],
        },
        "locked_version_ids": [reference["version_id"] for reference in references],
    }
