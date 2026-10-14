import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ScriptV1Schema } from '@ip-studio/contracts/script';
import { ScriptEditor } from './ScriptEditor';
import { Storyboard } from './Storyboard';

const script = ScriptV1Schema.parse({
  schema_version: '1.0',
  title: '在吗？',
  summary: '朋友来消息，卡仔还没准备好回应。',
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
      sent_at: '21:30',
    }],
    panels: [{
      action_id: '10000000-0000-4000-8000-000000000004',
      action: '卡仔看见手机上的新消息。',
      shot_type: 'close_up',
      character_version_ids: [],
      background_asset_version_id: null,
      no_text_prompt: '卡仔低头看手机，画面内不要出现任何文字。',
      dialogue_ids: ['10000000-0000-4000-8000-000000000002'],
    }],
  }],
});

describe('ScriptEditor', () => {
  afterEach(cleanup);

  it('edits structured dialogue and saves it as a new immutable revision', () => {
    const onSave = vi.fn();
    render(<ScriptEditor
      revisionNo={1}
      sourceMarkdown="朋友：在吗？"
      script={script}
      onSave={onSave}
    />);

    fireEvent.change(screen.getByLabelText('对白 · 朋友'), { target: { value: '还在吗？' } });
    fireEvent.click(screen.getByRole('button', { name: '保存为新修订' }));

    expect(onSave).toHaveBeenCalledWith(expect.objectContaining({
      base_revision: 1,
      source_markdown: '朋友：在吗？',
      script: expect.objectContaining({
        scenes: [expect.objectContaining({
          dialogues: [expect.objectContaining({ text: '还在吗？' })],
        })],
      }),
    }));
  });

  it('previews dialogue changes and waits for an explicit sync confirmation', async () => {
    const dialogueChange = {
      panel_order: 1,
      element_id: '10000000-0000-4000-8000-000000000005',
      old_text: '旧对白',
      new_text: '新对白',
    };
    const panel = {
      panel_id: script.scenes[0].panels[0].action_id,
      panel_order: 1,
      scene_id: script.scenes[0].scene_id,
      scene_name: '卧室',
      location: '卡仔的卧室',
      time: '夜晚',
      action: '卡仔看见手机上的新消息。',
      shot_type: 'close_up' as const,
      character_version_ids: [],
      background_asset_version_id: null,
      no_text_prompt: '无字画面。',
      dialogues: [script.scenes[0].dialogues[0]],
    };
    const conflict = Object.assign(new Error('剧本对白与画布中已有聊天文字不同'), {
      status: 409,
      detail: { dialogue_changes: [dialogueChange] },
    });
    const onMaterialize = vi.fn()
      .mockRejectedValueOnce(conflict)
      .mockResolvedValueOnce({
        script_revision_no: 2,
        document_revision: 2,
        panels: [panel],
        synced_dialogue_count: 1,
        dialogue_changes: [dialogueChange],
      });
    render(<Storyboard panels={[panel]} documentRevision={1} onMaterialize={onMaterialize} />);

    fireEvent.click(screen.getByRole('button', { name: '从剧本生成分镜卡' }));
    expect(await screen.findByRole('alertdialog')).toBeTruthy();
    const preview = screen.getByRole('alertdialog');
    expect(preview.textContent).toContain('旧对白');
    expect(preview.textContent).toContain('新对白');
    expect(onMaterialize).toHaveBeenLastCalledWith(1, false);

    fireEvent.click(screen.getByRole('button', { name: '确认并同步对白' }));
    expect((await screen.findByRole('status')).textContent).toContain('已同步 1 条对白');
    expect(onMaterialize).toHaveBeenLastCalledWith(1, true);
  });
});
