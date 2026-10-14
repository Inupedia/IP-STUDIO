import { useEffect, useState } from 'react';
import type { CodexCapabilityV1, CodexRunV1 } from '@ip-studio/contracts/codex';
import { api } from '../../lib/api';

export interface CodexStatusProps {
  taskId: string;
  canStart?: boolean;
  onCandidateReady?: () => void;
}

const capabilityLabels: Record<CodexCapabilityV1['status'], string> = {
  available: '已验证可用',
  unavailable: '当前不可用',
  needs_auth: '需要在本机 Codex 登录',
  unsupported: '当前 Codex 不支持 ImageGen',
};

function isTerminal(run: CodexRunV1): boolean {
  return run.status === 'candidate_ready' || run.status === 'failed';
}

export function CodexStatus({ taskId, canStart = true, onCandidateReady }: CodexStatusProps) {
  const [capability, setCapability] = useState<CodexCapabilityV1 | null>(null);
  const [run, setRun] = useState<CodexRunV1 | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    api.getCodexCapabilities()
      .then((report) => { if (active) setCapability(report); })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : '无法读取本机 Codex 能力');
      })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, []);

  useEffect(() => {
    if (!run || isTerminal(run)) return undefined;
    let active = true;
    const timer = window.setTimeout(() => {
      api.getCodexRun(run.run_id)
        .then((current) => {
          if (!active) return;
          setRun(current);
          if (current.status === 'candidate_ready') onCandidateReady?.();
        })
        .catch((cause: unknown) => {
          if (active) setError(cause instanceof Error ? cause.message : '无法读取 Codex 任务状态');
        });
    }, 1200);
    return () => {
      active = false;
      window.clearTimeout(timer);
    };
  }, [run, onCandidateReady]);

  async function probe() {
    setBusy(true);
    setError('');
    setRun(null);
    try {
      setCapability(await api.probeCodexCapabilities());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '本机 ImageGen 验证失败');
    } finally {
      setBusy(false);
    }
  }

  async function start() {
    setBusy(true);
    setError('');
    setRun(null);
    try {
      const started = await api.startCodexRun(taskId);
      setRun(started);
      if (started.status === 'candidate_ready') onCandidateReady?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法启动本机 Codex ImageGen');
    } finally {
      setBusy(false);
    }
  }

  async function cancel() {
    if (!run) return;
    setBusy(true);
    setError('');
    try {
      setRun(await api.cancelCodexRun(run.run_id));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法取消本机 Codex 生成');
    } finally {
      setBusy(false);
    }
  }

  const available = capability?.status === 'available' && capability.e2e_verified;

  return (
    <section className="codex-status" aria-label="本机 Codex ImageGen">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">CONDITIONAL LOCAL IMAGEGEN</p>
          <h3>本机 Codex ImageGen</h3>
        </div>
        <span role="status">
          {loading ? '正在检查…' : capability ? capabilityLabels[capability.status] : '状态未知'}
        </span>
      </div>
      <p className="generation-task-note">
        {capability?.reason ?? '能力读取失败时，仍可在上方使用 ChatGPT Web 手动生成并导入。'}
      </p>
      {capability?.codex_version && <small>已验证版本：{capability.codex_version}</small>}
      <div className="generation-task-actions">
        <button
          className="button button-secondary"
          type="button"
          disabled={busy || loading}
          onClick={() => void probe()}
        >
          {busy && !run ? '正在真实生成探测图…' : '验证本机 ImageGen 能力'}
        </button>
        {available && canStart && !run && (
          <button className="button button-primary" type="button" disabled={busy} onClick={() => void start()}>
            使用 Codex 生成候选
          </button>
        )}
        {run && (run.status === 'queued' || run.status === 'running') && (
          <button className="button button-secondary" type="button" disabled={busy} onClick={() => void cancel()}>
            取消 Codex 生成
          </button>
        )}
      </div>
      {run && (
        <p className={run.status === 'failed' ? 'form-error' : 'production-success'} role="status">
          {run.status === 'queued' && 'Codex 生图任务已排队…'}
          {run.status === 'running' && 'Codex 正在生成图片…'}
          {run.status === 'candidate_ready' && `候选已生成，等待人工审核${run.candidate_id ? ` · ${run.candidate_id}` : ''}`}
          {run.status === 'failed' && `Codex 生图失败：${run.error_reason ?? '请使用 ChatGPT Web 手动生成并导入。'}`}
        </p>
      )}
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
