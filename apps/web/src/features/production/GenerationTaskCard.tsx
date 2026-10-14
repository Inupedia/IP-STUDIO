import { useEffect, useState } from 'react';
import type { GenerationTaskV1 } from '@ip-studio/contracts/generation';
import { CodexStatus } from '../codex/CodexStatus';

export interface GenerationTaskCardProps {
  task: GenerationTaskV1;
  onStartManualGeneration: () => Promise<unknown>;
  onDownloadReferenceBundle: () => Promise<unknown>;
}

const statusLabels: Record<GenerationTaskV1['status'], string> = {
  prepared: '已准备',
  waiting_manual_generation: '人工生成中',
  asset_imported: '素材已导入',
};

function referenceLabel(kind: GenerationTaskV1['reference_snapshot'][number]['kind']): string {
  if (kind === 'character_version') return '角色版本';
  if (kind === 'style_version') return '画风版本';
  return '素材版本';
}

export function GenerationTaskCard({
  task,
  onStartManualGeneration,
  onDownloadReferenceBundle,
}: GenerationTaskCardProps) {
  const [taskStatus, setTaskStatus] = useState(task.status);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => setTaskStatus(task.status), [task.status]);

  async function copyPrompt() {
    setMessage('');
    setError('');
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(task.prompt_snapshot.text);
      setMessage('提示词已复制');
    } catch {
      setError('复制失败，可选中下方提示词手动复制。');
    }
  }

  async function startManualGeneration() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await onStartManualGeneration();
      setTaskStatus('waiting_manual_generation');
      setMessage('状态已更新：人工生成中。请在 ChatGPT Web 中手动粘贴提示词并导入结果。');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法更新任务状态');
    } finally {
      setBusy(false);
    }
  }

  async function downloadBundle() {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      await onDownloadReferenceBundle();
      setMessage('参考包已下载');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法下载参考包');
    } finally {
      setBusy(false);
    }
  }

  return (
    <article className="generation-task-card" aria-label="人工生图任务">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">MANUAL IMAGE GENERATION · {task.mode}</p>
          <h2>单格生图任务</h2>
        </div>
        <span className={`generation-task-status generation-task-status-${taskStatus}`} role="status">
          {statusLabels[taskStatus]}
        </span>
      </div>
      <p className="generation-task-note">
        这是人工任务卡。IP Studio 不会访问 ChatGPT 私有接口，也不会把订阅当作开发者 API；请在 ChatGPT Web 手动使用提示词与参考包。
      </p>
      <label className="generation-task-prompt">
        冻结提示词
        <textarea readOnly rows={9} value={task.prompt_snapshot.text} />
      </label>
      <div className="generation-task-references" aria-label="冻结参考版本">
        {task.reference_snapshot.length === 0 ? (
          <span className="storyboard-empty">此任务没有额外参考素材。</span>
        ) : task.reference_snapshot.map((reference) => (
          <span className="generation-reference-chip" key={`${reference.kind}:${reference.version_id}`}>
            {referenceLabel(reference.kind)} · V{reference.version_no} · {reference.name}
            <code>{reference.version_id}</code>
          </span>
        ))}
      </div>
      <div className="generation-task-actions">
        <button className="button button-secondary" type="button" onClick={() => void copyPrompt()}>
          复制提示词
        </button>
        <button className="button button-secondary" type="button" disabled={busy} onClick={() => void downloadBundle()}>
          下载参考包 ZIP
        </button>
        {taskStatus === 'prepared' && (
          <button className="button button-primary" type="button" disabled={busy} onClick={() => void startManualGeneration()}>
            {busy ? '正在更新…' : '我已在 ChatGPT Web 开始生成'}
          </button>
        )}
      </div>
      {message && <p className="production-success" role="status">{message}</p>}
      {error && <p className="form-error" role="alert">{error}</p>}
      <CodexStatus
        taskId={task.task_id}
        canStart={taskStatus === 'prepared' || taskStatus === 'asset_imported'}
        onCandidateReady={() => setTaskStatus('asset_imported')}
      />
    </article>
  );
}
