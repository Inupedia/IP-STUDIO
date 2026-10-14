import { useEffect, useState } from 'react';
import type { GenerationCandidateV1 } from '@ip-studio/contracts/generation';
import { api } from '../../lib/api';

export interface CandidateReviewProps {
  ipId: string;
  onReviewed?: () => void;
  refreshKey?: number;
}

const statusLabels: Record<GenerationCandidateV1['status'], string> = {
  pending_review: '待审核',
  approved: '已批准 · 可复用',
  rejected: '已拒绝',
};

export function CandidateReview({ ipId, onReviewed, refreshKey = 0 }: CandidateReviewProps) {
  const [candidates, setCandidates] = useState<GenerationCandidateV1[]>([]);
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [reviewNotes, setReviewNotes] = useState<Record<string, string>>({});
  const [loading, setLoading] = useState(true);
  const [busyCandidateId, setBusyCandidateId] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let active = true;
    setLoading(true);
    setError('');
    api.getGenerationCandidates(ipId)
      .then((items) => {
        if (active) setCandidates(items);
      })
      .catch((cause: unknown) => {
        if (active) setError(cause instanceof Error ? cause.message : '无法加载候选素材');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [ipId, refreshKey]);

  useEffect(() => {
    let active = true;
    const urls: string[] = [];
    setPreviews({});
    for (const candidate of candidates) {
      void api.getAssetPreview(ipId, candidate.asset_id, candidate.asset_version_id)
        .then((url) => {
          urls.push(url);
          if (active) setPreviews((current) => ({ ...current, [candidate.candidate_id]: url }));
          else if (url.startsWith('blob:')) URL.revokeObjectURL(url);
        })
        .catch(() => undefined);
    }
    return () => {
      active = false;
      urls.forEach((url) => { if (url.startsWith('blob:')) URL.revokeObjectURL(url); });
    };
  }, [candidates, ipId]);

  async function approve(candidate: GenerationCandidateV1) {
    setBusyCandidateId(candidate.candidate_id);
    setError('');
    try {
      const reviewed = await api.approveGenerationCandidate(candidate.candidate_id);
      setCandidates((current) => current.map((item) =>
        item.candidate_id === reviewed.candidate_id ? reviewed : item,
      ));
      onReviewed?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法批准候选素材');
    } finally {
      setBusyCandidateId('');
    }
  }

  async function reject(candidate: GenerationCandidateV1) {
    setBusyCandidateId(candidate.candidate_id);
    setError('');
    try {
      const reviewed = await api.rejectGenerationCandidate(
        candidate.candidate_id,
        reviewNotes[candidate.candidate_id] ?? '',
      );
      setCandidates((current) => current.map((item) =>
        item.candidate_id === reviewed.candidate_id ? reviewed : item,
      ));
      onReviewed?.();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法拒绝候选素材');
    } finally {
      setBusyCandidateId('');
    }
  }

  return (
    <section className="candidate-review" aria-label="候选素材审核">
      <div className="production-section-heading">
        <div>
          <p className="eyebrow">CANDIDATE LIBRARY</p>
          <h2>候选素材审核</h2>
        </div>
        <span>{candidates.length} 条审核记录</span>
      </div>
      {loading && <p role="status">正在读取候选素材…</p>}
      {!loading && candidates.length === 0 && (
        <p className="storyboard-empty">完成一次任务图片导入后，候选会显示在这里等待审核。</p>
      )}
      <div className="candidate-review-list">
        {candidates.map((candidate) => {
          const busy = busyCandidateId === candidate.candidate_id;
          return (
            <article className="candidate-review-card" key={candidate.candidate_id}>
              <div className="candidate-preview">
                {previews[candidate.candidate_id]
                  ? <img src={previews[candidate.candidate_id]} alt={`${candidate.asset_name} 候选预览`} />
                  : <span>图片预览加载中</span>}
              </div>
              <div className="candidate-review-content">
                <div className="storyboard-card-heading">
                  <strong>{candidate.asset_name} · V{candidate.version_no}</strong>
                  <span>{statusLabels[candidate.status]}</span>
                </div>
                <small>Panel {candidate.panel_id} · Task {candidate.task_id}</small>
                {candidate.review_note && <p className="candidate-review-note">审核意见：{candidate.review_note}</p>}
                {candidate.status === 'pending_review' && (
                  <>
                    <label className="candidate-review-reason">
                      拒绝原因
                      <textarea
                        aria-label={`拒绝原因 · ${candidate.asset_name}`}
                        rows={2}
                        maxLength={1000}
                        value={reviewNotes[candidate.candidate_id] ?? ''}
                        onChange={(event) => {
                          const value = event.currentTarget.value;
                          setReviewNotes((current) => ({
                            ...current,
                            [candidate.candidate_id]: value,
                          }));
                        }}
                      />
                    </label>
                    <div className="candidate-review-actions">
                      <button
                        className="button button-primary"
                        type="button"
                        disabled={busy}
                        onClick={() => void approve(candidate)}
                      >
                        {busy ? '正在保存…' : `批准并加入可复用素材 · ${candidate.asset_name}`}
                      </button>
                      <button
                        className="button button-secondary"
                        type="button"
                        disabled={busy}
                        onClick={() => void reject(candidate)}
                      >
                        {busy ? '正在保存…' : `拒绝候选 · ${candidate.asset_name}`}
                      </button>
                    </div>
                  </>
                )}
                {candidate.status === 'approved' && (
                  <p className="production-success">已加入同 IP 的批准素材库；替换画格时会作为独立位图版本使用。</p>
                )}
              </div>
            </article>
          );
        })}
      </div>
      <p className="candidate-review-footnote">
        旧的整页扁平图片只能作为参考素材导入；审核或替换不会把位图拆成可逐笔编辑图层。
      </p>
      {error && <p className="form-error" role="alert">{error}</p>}
    </section>
  );
}
