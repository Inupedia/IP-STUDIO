import { useEffect, useState, type FormEvent } from 'react';
import { ScriptV1Schema } from '@ip-studio/contracts/script';
import type { ScriptV1 } from '@ip-studio/contracts/script';

export interface ScriptSavePayload {
  base_revision: number;
  source_markdown: string;
  script: ScriptV1;
}

export interface ScriptEditorProps {
  revisionNo: number;
  sourceMarkdown: string;
  script: ScriptV1;
  onSave: (payload: ScriptSavePayload) => void | Promise<void>;
  saving?: boolean;
}

function newId(): string {
  return crypto.randomUUID();
}

export function ScriptEditor({ revisionNo, sourceMarkdown, script, onSave, saving = false }: ScriptEditorProps) {
  const [draft, setDraft] = useState(() => ScriptV1Schema.parse(script));
  const [markdown, setMarkdown] = useState(sourceMarkdown);
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    setDraft(ScriptV1Schema.parse(script));
    setMarkdown(sourceMarkdown);
  }, [revisionNo, script, sourceMarkdown]);

  function patchScene(sceneIndex: number, patch: Partial<ScriptV1['scenes'][number]>) {
    setDraft((current) => ({
      ...current,
      scenes: current.scenes.map((scene, index) => index === sceneIndex ? { ...scene, ...patch } : scene),
    }));
  }

  function patchDialogue(
    sceneIndex: number,
    dialogueIndex: number,
    patch: Partial<ScriptV1['scenes'][number]['dialogues'][number]>,
  ) {
    setDraft((current) => ({
      ...current,
      scenes: current.scenes.map((scene, index) => index === sceneIndex
        ? { ...scene, dialogues: scene.dialogues.map((dialogue, line) => line === dialogueIndex ? { ...dialogue, ...patch } : dialogue) }
        : scene),
    }));
  }

  function patchPanel(sceneIndex: number, panelIndex: number, patch: Partial<ScriptV1['scenes'][number]['panels'][number]>) {
    setDraft((current) => ({
      ...current,
      scenes: current.scenes.map((scene, index) => index === sceneIndex
        ? { ...scene, panels: scene.panels.map((panel, line) => line === panelIndex ? { ...panel, ...patch } : panel) }
        : scene),
    }));
  }

  function addScene() {
    setDraft((current) => ScriptV1Schema.parse({
      ...current,
      scenes: [...current.scenes, {
        scene_id: newId(),
        name: `场景 ${current.scenes.length + 1}`,
        location: '',
        time: '',
        action: '',
        character_version_ids: [],
        dialogues: [],
        panels: [],
      }],
    }));
  }

  function addDialogue(sceneIndex: number) {
    const dialogueId = newId();
    setDraft((current) => ({
      ...current,
      scenes: current.scenes.map((scene, index) => {
        if (index !== sceneIndex) return scene;
        const dialogue = {
          dialogue_id: dialogueId,
          speaker_id: newId(),
          speaker_name: '角色',
          character_version_id: null,
          text: '',
          kind: 'speech_bubble' as const,
          sent_at: null,
        };
        return {
          ...scene,
          dialogues: [...scene.dialogues, dialogue],
          panels: scene.panels.map((panel, panelIndex) => panelIndex === 0
            ? { ...panel, dialogue_ids: [...panel.dialogue_ids, dialogueId] }
            : panel),
        };
      }),
    }));
  }

  function addPanel(sceneIndex: number) {
    setDraft((current) => ({
      ...current,
      scenes: current.scenes.map((scene, index) => index === sceneIndex
        ? {
          ...scene,
          panels: [...scene.panels, {
            action_id: newId(),
            action: '',
            shot_type: 'medium',
            character_version_ids: scene.character_version_ids,
            background_asset_version_id: null,
            no_text_prompt: '只绘制画面，不要在图片中生成任何文字、气泡、页码或水印。',
            dialogue_ids: scene.dialogues.map((dialogue) => dialogue.dialogue_id),
          }],
        }
        : scene),
    }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      await onSave({ base_revision: revisionNo, source_markdown: markdown, script: ScriptV1Schema.parse(draft) });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法保存新的剧本修订');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <form className="script-editor" aria-label="结构化剧本编辑器" onSubmit={submit}>
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">SCRIPT REVISION · V{revisionNo}</p>
          <h2>剧本与分镜规划</h2>
        </div>
        <button className="button button-primary" type="submit" disabled={saving || submitting}>
          {saving || submitting ? '正在保存…' : '保存为新修订'}
        </button>
      </div>
      <label>
        分集标题
        <input
          aria-label="分集标题"
          maxLength={200}
          value={draft.title}
          onChange={(event) => setDraft((current) => ({ ...current, title: event.currentTarget.value }))}
        />
      </label>
      <label>
        故事概要
        <textarea
          aria-label="故事概要"
          rows={2}
          maxLength={4000}
          value={draft.summary}
          onChange={(event) => setDraft((current) => ({ ...current, summary: event.currentTarget.value }))}
        />
      </label>
      <label>
        原始 Markdown
        <textarea
          aria-label="剧本 Markdown"
          rows={5}
          maxLength={100000}
          value={markdown}
          onChange={(event) => setMarkdown(event.currentTarget.value)}
          placeholder="粘贴或手写 Markdown 剧本；结构化场景与对白在下方单独编辑。"
        />
      </label>
      {draft.scenes.map((scene, sceneIndex) => (
        <fieldset className="script-scene-card" key={scene.scene_id}>
          <legend>场景 {sceneIndex + 1}</legend>
          <div className="script-field-grid">
            <label>
              场景名称
              <input value={scene.name} maxLength={120} onChange={(event) => patchScene(sceneIndex, { name: event.currentTarget.value })} />
            </label>
            <label>
              地点
              <input value={scene.location} maxLength={500} onChange={(event) => patchScene(sceneIndex, { location: event.currentTarget.value })} />
            </label>
            <label>
              时间
              <input value={scene.time} maxLength={120} onChange={(event) => patchScene(sceneIndex, { time: event.currentTarget.value })} />
            </label>
          </div>
          <label>
            剧情动作
            <textarea aria-label={`剧情动作 · ${scene.name}`} rows={2} maxLength={4000} value={scene.action} onChange={(event) => patchScene(sceneIndex, { action: event.currentTarget.value })} />
          </label>
          <div className="script-subsection-heading">
            <strong>对白</strong>
            <button type="button" className="text-button" onClick={() => addDialogue(sceneIndex)}>＋ 添加对白</button>
          </div>
          {scene.dialogues.map((dialogue, dialogueIndex) => (
            <div className="script-dialogue-fields" key={dialogue.dialogue_id}>
              <div className="script-field-grid">
                <label>
                  说话人
                  <input value={dialogue.speaker_name} maxLength={120} onChange={(event) => patchDialogue(sceneIndex, dialogueIndex, { speaker_name: event.currentTarget.value })} />
                </label>
                <label>
                  对白类型
                  <select
                    aria-label={`对白类型 · ${dialogue.speaker_name}`}
                    value={dialogue.kind}
                    onChange={(event) => patchDialogue(sceneIndex, dialogueIndex, { kind: event.currentTarget.value as typeof dialogue.kind })}
                  >
                    <option value="speech_bubble">普通气泡</option>
                    <option value="chat_message">聊天消息</option>
                  </select>
                </label>
                {dialogue.kind === 'chat_message' && (
                  <label>
                    时间
                    <input value={dialogue.sent_at ?? ''} maxLength={40} onChange={(event) => patchDialogue(sceneIndex, dialogueIndex, { sent_at: event.currentTarget.value || null })} />
                  </label>
                )}
              </div>
              <label>
                {`对白 · ${dialogue.speaker_name}`}
                <textarea
                  aria-label={`对白 · ${dialogue.speaker_name}`}
                  rows={2}
                  maxLength={10000}
                  value={dialogue.text}
                  onChange={(event) => patchDialogue(sceneIndex, dialogueIndex, { text: event.currentTarget.value })}
                />
              </label>
            </div>
          ))}
          <div className="script-subsection-heading">
            <strong>待绘制画格动作</strong>
            <button type="button" className="text-button" onClick={() => addPanel(sceneIndex)}>＋ 添加画格卡</button>
          </div>
          {scene.panels.map((panel, panelIndex) => (
            <div className="script-panel-plan" key={panel.action_id}>
              <label>
                镜头动作
                <textarea aria-label="分镜动作" rows={2} maxLength={4000} value={panel.action} onChange={(event) => patchPanel(sceneIndex, panelIndex, { action: event.currentTarget.value })} />
              </label>
              <label>
                镜头类型
                <select value={panel.shot_type} onChange={(event) => patchPanel(sceneIndex, panelIndex, { shot_type: event.currentTarget.value as typeof panel.shot_type })}>
                  <option value="wide">远景</option>
                  <option value="medium">中景</option>
                  <option value="close_up">近景</option>
                  <option value="extreme_close_up">特写</option>
                  <option value="over_the_shoulder">过肩镜头</option>
                  <option value="top_down">俯视</option>
                </select>
              </label>
              <label>
                无字画面提示
                <textarea aria-label="无字画面提示" rows={3} maxLength={5000} value={panel.no_text_prompt} onChange={(event) => patchPanel(sceneIndex, panelIndex, { no_text_prompt: event.currentTarget.value })} />
              </label>
            </div>
          ))}
        </fieldset>
      ))}
      <button type="button" className="button button-secondary" onClick={addScene}>＋ 添加场景</button>
      {error && <p className="form-error" role="alert">{error}</p>}
      <p className="script-immutability-note">保存会追加一个新修订；已经保存的剧本版本不会被覆盖，画布对白需在分镜同步时单独确认。</p>
    </form>
  );
}
