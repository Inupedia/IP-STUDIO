import { useState, type FormEvent } from 'react';
import type { IP, IPCreate } from '@ip-studio/contracts/domain';

export interface IpListProps {
  ips: IP[];
  selectedIpId: string;
  onSelect: (ipId: string) => void;
  onCreate: (payload: IPCreate) => Promise<void>;
}

export function IpList({ ips, selectedIpId, onSelect, onCreate }: IpListProps) {
  const [isCreating, setIsCreating] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [summary, setSummary] = useState('');
  const [error, setError] = useState('');

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError('');
    try {
      await onCreate({ code, name, summary: summary || null });
      setCode('');
      setName('');
      setSummary('');
      setIsCreating(false);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '无法创建 IP');
    }
  }

  return (
    <aside className="ip-rail" aria-label="IP 列表">
      <div className="rail-heading">
        <p className="eyebrow">工作室</p>
        <h2>我的 IP</h2>
      </div>
      <nav className="ip-list" aria-label="选择 IP">
        {ips.map((ip) => (
          <button
            className={`ip-list-item${selectedIpId === ip.id ? ' is-selected' : ''}`}
            key={ip.id}
            type="button"
            aria-current={selectedIpId === ip.id ? 'page' : undefined}
            onClick={() => onSelect(ip.id)}
          >
            <span className="ip-avatar" aria-hidden="true">{ip.code.slice(0, 2)}</span>
            <span className="ip-copy">
              <strong>{ip.name}</strong>
              <small>{ip.code}</small>
            </span>
            <span className="ip-chevron" aria-hidden="true">↗</span>
          </button>
        ))}
      </nav>
      {isCreating ? (
        <form className="create-ip-form" onSubmit={submit}>
          <label>
            编号
            <input
              required
              maxLength={32}
              value={code}
              onChange={(event) => setCode(event.currentTarget.value)}
              placeholder="KAZI"
            />
          </label>
          <label>
            名称
            <input
              required
              maxLength={120}
              value={name}
              onChange={(event) => setName(event.currentTarget.value)}
              placeholder="人间卡顿局"
            />
          </label>
          <label>
            简介
            <textarea
              rows={2}
              maxLength={4000}
              value={summary}
              onChange={(event) => setSummary(event.currentTarget.value)}
            />
          </label>
          {error && <p className="form-error" role="alert">{error}</p>}
          <div className="form-actions">
            <button className="button button-quiet" type="button" onClick={() => setIsCreating(false)}>
              取消
            </button>
            <button className="button button-primary" type="submit">创建</button>
          </div>
        </form>
      ) : (
        <button className="add-ip-button" type="button" onClick={() => setIsCreating(true)}>
          <span aria-hidden="true">＋</span>
          新建 IP
        </button>
      )}
      <div className="rail-footnote">
        <span className="rail-status-dot" aria-hidden="true" />
        <span>本机工作区</span>
      </div>
    </aside>
  );
}
