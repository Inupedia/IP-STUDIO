import { z } from 'zod';

const idSchema = z.uuid();

export const ScriptDialogueV1Schema = z.object({
  dialogue_id: idSchema,
  speaker_id: idSchema,
  speaker_name: z.string().min(1).max(120),
  character_version_id: idSchema.nullable().default(null),
  text: z.string().max(10000),
  kind: z.enum(['speech_bubble', 'chat_message']),
  sent_at: z.string().max(40).nullable().default(null),
}).strict();

export const StoryboardActionV1Schema = z.object({
  action_id: idSchema,
  action: z.string().min(1).max(4000),
  shot_type: z.enum(['wide', 'medium', 'close_up', 'extreme_close_up', 'over_the_shoulder', 'top_down']),
  character_version_ids: z.array(idSchema).max(20),
  background_asset_version_id: idSchema.nullable().default(null),
  no_text_prompt: z.string().min(1).max(5000),
  dialogue_ids: z.array(idSchema).max(100),
}).strict();

export const ScriptSceneV1Schema = z.object({
  scene_id: idSchema,
  name: z.string().min(1).max(120),
  location: z.string().max(500),
  time: z.string().max(120),
  action: z.string().max(4000),
  character_version_ids: z.array(idSchema).max(20),
  dialogues: z.array(ScriptDialogueV1Schema).max(500),
  panels: z.array(StoryboardActionV1Schema).max(100),
}).strict();

export const ScriptV1Schema = z.object({
  schema_version: z.literal('1.0'),
  title: z.string().min(1).max(200),
  summary: z.string().max(4000),
  theme_tags: z.array(z.string().min(1).max(48)).max(40),
  scenes: z.array(ScriptSceneV1Schema).min(1).max(100),
}).strict().superRefine((script, context) => {
  const ids = new Set<string>();
  script.scenes.forEach((scene, sceneIndex) => {
    if (ids.has(scene.scene_id)) {
      context.addIssue({ code: 'custom', message: 'Scene ids must be unique', path: ['scenes', sceneIndex, 'scene_id'] });
    }
    ids.add(scene.scene_id);
    const dialogueIds = new Set(scene.dialogues.map((dialogue) => dialogue.dialogue_id));
    scene.dialogues.forEach((dialogue, dialogueIndex) => {
      if (ids.has(dialogue.dialogue_id)) {
        context.addIssue({ code: 'custom', message: 'Script ids must be unique', path: ['scenes', sceneIndex, 'dialogues', dialogueIndex, 'dialogue_id'] });
      }
      ids.add(dialogue.dialogue_id);
    });
    scene.panels.forEach((panel, panelIndex) => {
      if (ids.has(panel.action_id)) {
        context.addIssue({ code: 'custom', message: 'Script ids must be unique', path: ['scenes', sceneIndex, 'panels', panelIndex, 'action_id'] });
      }
      ids.add(panel.action_id);
      if (panel.dialogue_ids.some((dialogueId) => !dialogueIds.has(dialogueId))) {
        context.addIssue({ code: 'custom', message: 'Panel dialogue ids must refer to a dialogue in the same scene', path: ['scenes', sceneIndex, 'panels', panelIndex, 'dialogue_ids'] });
      }
    });
  });
});

export type ScriptDialogueV1 = z.infer<typeof ScriptDialogueV1Schema>;
export type StoryboardActionV1 = z.infer<typeof StoryboardActionV1Schema>;
export type ScriptSceneV1 = z.infer<typeof ScriptSceneV1Schema>;
export type ScriptV1 = z.infer<typeof ScriptV1Schema>;

export interface ScriptRevisionReadV1 {
  revision_id: string;
  revision_no: number;
  source_markdown: string | null;
  script: ScriptV1;
  note: string | null;
  created_at: string;
}

export interface StoryboardPanelV1 {
  panel_id: string;
  panel_order: number;
  scene_id: string;
  scene_name: string;
  location: string;
  time: string;
  action: string;
  shot_type: StoryboardActionV1['shot_type'];
  character_version_ids: string[];
  background_asset_version_id: string | null;
  no_text_prompt: string;
  dialogues: ScriptDialogueV1[];
}

export interface ScriptMaterializationResultV1 {
  script_revision_no: number;
  document_revision: number;
  panels: StoryboardPanelV1[];
  synced_dialogue_count: number;
  dialogue_changes: Array<{
    panel_order: number;
    element_id: string;
    old_text: string;
    new_text: string;
  }>;
}
