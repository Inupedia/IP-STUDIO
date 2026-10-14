from uuid import uuid4

from app.services.prompt_builder import build_prompt


def test_prompt_contains_locked_version_ids_and_excludes_dialogue_text() -> None:
    character_version_id = uuid4()
    style_version_id = uuid4()
    panel = {
        "panel_id": uuid4(),
        "panel_order": 1,
        "scene_name": "卧室",
        "location": "卡仔的卧室",
        "time": "夜晚",
        "action": "卡仔低头看手机。",
        "shot_type": "close_up",
        "no_text_prompt": "卡仔低头看手机，画面内不要出现任何文字。",
        "character_version_ids": [character_version_id],
        "dialogues": [{"text": "绝对不能泄露的对白：在吗？"}],
    }
    references = [
        {
            "kind": "character_version",
            "version_id": str(character_version_id),
            "version_no": 3,
            "name": "卡仔",
            "bible_summary": "圆脸",
        },
        {
            "kind": "style_version",
            "version_id": str(style_version_id),
            "version_no": 2,
            "name": "清爽漫画",
            "bible_summary": "干净线条",
        },
    ]

    snapshot = build_prompt(panel, references)

    assert str(character_version_id) in snapshot["text"]
    assert str(style_version_id) in snapshot["text"]
    assert "单格" in snapshot["text"]
    assert "页码" in snapshot["text"]
    assert "水印" in snapshot["text"]
    assert "任何文字" in snapshot["text"]
    assert "绝对不能泄露" not in snapshot["text"]
    assert "在吗？" not in snapshot["text"]
