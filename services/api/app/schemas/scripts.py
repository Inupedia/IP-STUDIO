from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ScriptDialogue(StrictModel):
    dialogue_id: UUID
    speaker_id: UUID
    speaker_name: str = Field(min_length=1, max_length=120)
    character_version_id: UUID | None = None
    text: str = Field(max_length=10_000)
    kind: Literal["speech_bubble", "chat_message"]
    sent_at: str | None = Field(default=None, max_length=40)


class StoryboardAction(StrictModel):
    action_id: UUID
    action: str = Field(min_length=1, max_length=4_000)
    shot_type: Literal[
        "wide", "medium", "close_up", "extreme_close_up", "over_the_shoulder", "top_down"
    ]
    character_version_ids: list[UUID] = Field(max_length=20)
    background_asset_version_id: UUID | None = None
    no_text_prompt: str = Field(min_length=1, max_length=5_000)
    dialogue_ids: list[UUID] = Field(max_length=100)


class ScriptScene(StrictModel):
    scene_id: UUID
    name: str = Field(min_length=1, max_length=120)
    location: str = Field(max_length=500)
    time: str = Field(max_length=120)
    action: str = Field(max_length=4_000)
    character_version_ids: list[UUID] = Field(max_length=20)
    dialogues: list[ScriptDialogue] = Field(max_length=500)
    panels: list[StoryboardAction] = Field(max_length=100)

    @model_validator(mode="after")
    def panel_dialogues_exist_in_scene(self) -> "ScriptScene":
        dialogue_ids = {dialogue.dialogue_id for dialogue in self.dialogues}
        for panel in self.panels:
            if any(dialogue_id not in dialogue_ids for dialogue_id in panel.dialogue_ids):
                raise ValueError("Panel dialogue ids must refer to a dialogue in the same scene")
        return self


class ScriptV1(StrictModel):
    schema_version: Literal["1.0"]
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(max_length=4_000)
    theme_tags: list[str] = Field(max_length=40)
    scenes: list[ScriptScene] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def ids_are_unique(self) -> "ScriptV1":
        ids: list[UUID] = []
        for scene in self.scenes:
            ids.append(scene.scene_id)
            ids.extend(dialogue.dialogue_id for dialogue in scene.dialogues)
            ids.extend(panel.action_id for panel in scene.panels)
        if len(ids) != len(set(ids)):
            raise ValueError("Scene, dialogue, and panel ids must be unique")
        return self


class ScriptRevisionCreate(StrictModel):
    base_revision: int = Field(ge=0)
    source_markdown: str | None = Field(default=None, max_length=100_000)
    note: str | None = Field(default=None, max_length=500)
    script: ScriptV1


class ScriptRevisionRead(StrictModel):
    revision_id: UUID
    revision_no: int
    source_markdown: str | None
    script: ScriptV1
    note: str | None
    created_at: datetime


class MaterializePanelsRequest(StrictModel):
    base_document_revision: int = Field(ge=0)
    confirm_dialogue_sync: bool = False


class DialogueChange(StrictModel):
    panel_order: int
    element_id: UUID
    old_text: str
    new_text: str


class StoryboardPanelRead(StrictModel):
    panel_id: UUID
    panel_order: int
    scene_id: UUID
    scene_name: str
    location: str
    time: str
    action: str
    shot_type: Literal[
        "wide", "medium", "close_up", "extreme_close_up", "over_the_shoulder", "top_down"
    ]
    character_version_ids: list[UUID]
    background_asset_version_id: UUID | None
    no_text_prompt: str
    dialogues: list[ScriptDialogue]


class ScriptMaterializationResult(StrictModel):
    script_revision_no: int
    document_revision: int
    panels: list[StoryboardPanelRead]
    synced_dialogue_count: int
    dialogue_changes: list[DialogueChange]
