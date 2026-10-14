import { useEffect, useState } from 'react';
import type { ScriptMaterializationResultV1, StoryboardPanelV1 } from '@ip-studio/contracts/script';

interface DialogueChange {
  panel_order: number;
  element_id: string;
  old_text: string;
  new_text: string;
}

export interface StoryboardProps {
  panels: StoryboardPanelV1[];
  documentRevision: number;
  onMaterialize: (
    baseDocumentRevision: number,
    confirmDialogueSync: boolean,
  ) => Promise<ScriptMaterializationResultV1>;
}

function getDialogueChanges(cause: unknown): DialogueChange[] | null {
  if (typeof cause !== 'object' || cause === null || !('detail' in cause)) return null;
  const detail = cause.detail;
  if (typeof detail !== 'object' || detail === null || !('dialogue_changes' in detail)) return null;
  return Array.isArray(detail.dialogue_changes) ? detail.dialogue_changes as DialogueChange[] : null;
}

export function Storyboard({ panels, documentRevision, onMaterialize }: StoryboardProps) {
  const [materializedPanels, setMaterializedPanels] = useState(panels);
  const [currentDocumentRevision, setCurrentDocumentRevision] = useState(documentRevision);
  const [changes, setChanges] = useState<DialogueChange[] | null>(null);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setMaterializedPanels(panels);
    setCurrentDocumentRevision(documentRevision);
  }, [panels, documentRevision]);

  async function materialize(confirmDialogueSync: boolean) {
    setSaving(true);
    setError('');
    try {
      const result = await onMaterialize(currentDocumentRevision, confirmDialogueSync);
      setMaterializedPanels(result.panels);
      setCurrentDocumentRevision(result.document_revision);
      setChanges(null);
      setMessage(result.synced_dialogue_count > 0
        ? `已同步 ${result.synced_dialogue_count} 条对白；当前画布修订为 ${result.document_revision}。`
        : `已生成 ${result.panels.length} 张待绘制分镜卡。`);
    } catch (cause) {
      const nextChanges = getDialogueChanges(cause);
      if (nextChanges) {
        setChanges(nextChanges);
        setMessage('');
      } else {
        setError(cause instanceof Error ? cause.message : '无法生成分镜卡');
      }
    } finally {
      setSaving(false);
    }
  }

  return (
    <section className="storyboard" aria-label="分镜卡">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">PANEL PLANNING</p>
          <h2>待绘制分镜卡</h2>
        </div>
        <button
          className="button button-secondary"
          type="button"
          disabled={saving}
          onClick={() => void materialize(false)}
        >
          {saving ? '正在生成…' : '从剧本生成分镜卡'}
        </button>
      </div>
      {materializedPanels.length === 0 ? (
        <p className="storyboard-empty">保存结构化场景后，可将场景动作转换为待绘制的画格卡片。</p>
      ) : (
        <div className="storyboard-cards">
          {materializedPanels.map((panel) => (
            <article className="storyboard-card" key={panel.panel_id}>
              <div className="storyboard-card-heading">
                <strong>P{String(panel.panel_order).padStart(2, '0')} · {panel.scene_name}</strong>
                <span>{panel.shot_type}</span>
              </div>
              <p>{panel.action}</p>
              <small>{panel.location} · {panel.time}</small>
              <p className="storyboard-prompt-label">无字画面提示</p>
              <p className="storyboard-prompt">{panel.no_text_prompt}</p>
              {panel.dialogues.length > 0 && (
                <div className="storyboard-dialogues">
                  {panel.dialogues.map((dialogue) => (
                    <p key={dialogue.dialogue_id}><strong>{dialogue.speaker_name}：</strong>{dialogue.text}</p>
                  ))}
                </div>
              )}
            </article>
          ))}
        </div>
      )}
      {changes && (
        <div className="script-sync-preview" role="alertdialog" aria-labelledby="script-sync-title">
          <h3 id="script-sync-title">确认同步画布对白</h3>
          <p>剧本与已布置的聊天文字有 {changes.length} 处差异。只有确认后才会新增画布修订并更新这些文字对象。</p>
          <ul>
            {changes.map((change) => (
              <li key={change.element_id}>
                <span>格 {change.panel_order}：{change.old_text || '（空）'}</span>
                <span aria-hidden="true">→</span>
                <strong>{change.new_text || '（空）'}</strong>
              </li>
            ))}
          </ul>
          <div className="script-sync-actions">
            <button className="button button-primary" type="button" disabled={saving} onClick={() => void materialize(true)}>
              {saving ? '正在同步…' : '确认并同步对白'}
            </button>
            <button className="text-button" type="button" disabled={saving} onClick={() => setChanges(null)}>保留现有画布文字</button>
          </div>
        </div>
      )}
      {message && <p className="production-success" role="status">{message}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
