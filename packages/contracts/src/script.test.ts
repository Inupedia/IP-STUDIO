import { describe, expect, it } from 'vitest';
import { ScriptV1Schema } from './script';

const validScript = {
  schema_version: '1.0',
  title: '在吗？',
  summary: '朋友来消息。',
  theme_tags: ['日常'],
  scenes: [{
    scene_id: '10000000-0000-4000-8000-000000000001',
    name: '卧室',
    location: '卡仔的卧室',
    time: '夜晚',
    action: '卡仔低头看手机。',
    character_version_ids: [],
    dialogues: [{
      dialogue_id: '10000000-0000-4000-8000-000000000002',
      speaker_id: '10000000-0000-4000-8000-000000000003',
      speaker_name: '朋友',
      text: '在吗？',
      kind: 'chat_message',
    }],
    panels: [{
      action_id: '10000000-0000-4000-8000-000000000004',
      action: '卡仔看见新消息。',
      shot_type: 'close_up',
      character_version_ids: [],
      background_asset_version_id: null,
      no_text_prompt: '卡仔看手机，图内不要出现任何文字。',
      dialogue_ids: ['10000000-0000-4000-8000-000000000002'],
    }],
  }],
};

describe('ScriptV1 schema', () => {
  it('accepts structured scenes, dialogue and no-text storyboard plans', () => {
    const parsed = ScriptV1Schema.parse(validScript);
    expect(parsed.scenes[0].panels[0].dialogue_ids).toEqual([parsed.scenes[0].dialogues[0].dialogue_id]);
    expect(parsed.scenes[0].dialogues[0].character_version_id).toBeNull();
  });

  it('rejects panel dialogue ids that point outside their scene', () => {
    const invalidScript = structuredClone(validScript);
    invalidScript.scenes[0].panels[0].dialogue_ids = ['10000000-0000-4000-8000-000000000099'];
    expect(() => ScriptV1Schema.parse(invalidScript)).toThrow(/same scene/);
  });
});
