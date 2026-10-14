import { lazy, Suspense, useEffect, useState, type FormEvent } from 'react';
import type { AdminProfile, IP } from '@ip-studio/contracts/domain';
import { AssetLibrary } from './features/assets/AssetLibrary';
import { BibleEditor } from './features/bibles/BibleEditor';
import { IpList } from './features/ips/IpList';
import { ApiError, api, authExpiredEvent, getAccessToken, setAccessToken } from './lib/api';

type WorkspaceView = 'assets' | 'bibles' | 'comics';
const ComicWorkspace = lazy(() => import('./features/story/ComicWorkspace').then((module) => ({ default: module.ComicWorkspace })));

function Brand() {
  return (
    <a className="wordmark" href="/" aria-label="IP Studio 首页">
      <span className="wordmark-mark" aria-hidden="true">IP</span>
      <span>STUDIO</span>
    </a>
  );
}

function LoginPanel({ onAuthenticated }: { onAuthenticated: (token: string) => void }) {
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError('');
    try {
      const token = await api.login(email, password);
      onAuthenticated(token.access_token);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '登录失败');
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-layout" aria-labelledby="workspace-title">
      <section className="login-intro">
        <p className="eyebrow">原创 IP 创作工作台</p>
        <h1 id="workspace-title">IP Studio</h1>
        <p>在一个安静、可追溯的工作区里维护角色、素材与漫画创作规范。</p>
        <div className="login-note">
          <span className="login-note-mark" aria-hidden="true">01</span>
          <span>工作室管理员登录<br />你的项目素材保存在本机配置的数据目录中。</span>
        </div>
      </section>
      <form className="login-card" onSubmit={submit}>
        <p className="eyebrow">工作室账户</p>
        <h2>继续工作</h2>
        <label>
          管理员邮箱
          <input
            autoComplete="username"
            autoFocus
            required
            type="email"
            value={email}
            onChange={(event) => setEmail(event.currentTarget.value)}
            placeholder="you@example.com"
          />
        </label>
        <label>
          密码
          <input
            autoComplete="current-password"
            required
            type="password"
            value={password}
            onChange={(event) => setPassword(event.currentTarget.value)}
            placeholder="输入管理员密码"
          />
        </label>
        {error && <p role="alert" className="form-error">{error}</p>}
        <button className="button button-primary login-submit" type="submit" disabled={submitting}>
          {submitting ? '正在验证…' : '登录工作室'}
        </button>
        <p className="login-footnote">登录凭据只发送到你配置的 IP Studio API。</p>
      </form>
    </main>
  );
}

export default function App() {
  const [token, setToken] = useState<string | null>(() => getAccessToken());
  const [admin, setAdmin] = useState<AdminProfile | null>(null);
  const [ips, setIps] = useState<IP[]>([]);
  const [selectedIpId, setSelectedIpId] = useState('');
  const [view, setView] = useState<WorkspaceView>('assets');
  const [comicWorkspaceDirty, setComicWorkspaceDirty] = useState(false);
  const [loading, setLoading] = useState(Boolean(token));
  const [error, setError] = useState('');

  useEffect(() => {
    if (!comicWorkspaceDirty) return;
    const warnBeforeUnload = (event: BeforeUnloadEvent) => {
      event.preventDefault();
      event.returnValue = '';
    };
    window.addEventListener('beforeunload', warnBeforeUnload);
    return () => window.removeEventListener('beforeunload', warnBeforeUnload);
  }, [comicWorkspaceDirty]);

  useEffect(() => {
    const onExpired = () => setToken(null);
    window.addEventListener(authExpiredEvent, onExpired);
    return () => window.removeEventListener(authExpiredEvent, onExpired);
  }, []);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setAdmin(null);
      setIps([]);
      setSelectedIpId('');
      return;
    }
    let active = true;
    setLoading(true);
    Promise.all([api.getCurrentAdmin(), api.getIps()])
      .then(([profile, availableIps]) => {
        if (!active) return;
        setAdmin(profile);
        setIps(availableIps);
        setSelectedIpId((current) =>
          availableIps.some((ip) => ip.id === current) ? current : availableIps[0]?.id ?? '',
        );
        setError('');
      })
      .catch((cause: unknown) => {
        if (!active) return;
        if (cause instanceof ApiError && cause.status === 401) {
          setAccessToken(null);
          setToken(null);
          return;
        }
        setError(cause instanceof Error ? cause.message : '无法连接到 IP Studio API');
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [token]);

  function confirmLeaveComicWorkspace() {
    if (view !== 'comics' || !comicWorkspaceDirty) return true;
    const discard = window.confirm('漫画工作台有未保存内容。离开会丢弃这些更改，仍要继续吗？');
    if (discard) setComicWorkspaceDirty(false);
    return discard;
  }

  function changeView(nextView: WorkspaceView) {
    if (nextView === view || !confirmLeaveComicWorkspace()) return;
    setView(nextView);
  }

  function changeSelectedIp(nextIpId: string) {
    if (nextIpId === selectedIpId || !confirmLeaveComicWorkspace()) return;
    setSelectedIpId(nextIpId);
  }

  async function createIp(payload: { code: string; name: string; summary?: string | null }) {
    if (!confirmLeaveComicWorkspace()) return;
    const created = await api.createIp(payload);
    setIps((current) => [...current, created]);
    setSelectedIpId(created.id);
  }

  function signOut() {
    if (!confirmLeaveComicWorkspace()) return;
    setAccessToken(null);
    setToken(null);
    setAdmin(null);
  }

  function updateDefaultStyle(versionId: string) {
    setIps((current) => current.map((ip) =>
      ip.id === selectedIpId ? { ...ip, default_style_version_id: versionId } : ip,
    ));
  }

  const selectedIp = ips.find((ip) => ip.id === selectedIpId) ?? null;

  return (
    <div className="app-shell">
      <header className="topbar">
        <Brand />
        <span className="topbar-context">原创 IP 创作工作台</span>
        {token && (
          <div className="topbar-account">
            {admin && <span className="account-email">{admin.email}</span>}
            <button className="text-button sign-out" type="button" onClick={signOut}>退出</button>
          </div>
        )}
      </header>

      {!token ? (
        <LoginPanel onAuthenticated={(nextToken) => setToken(nextToken)} />
      ) : loading ? (
        <main className="loading-workspace" role="status">正在打开工作室…</main>
      ) : (
        <div className="workspace-layout">
          <IpList
            ips={ips}
            selectedIpId={selectedIpId}
            onSelect={changeSelectedIp}
            onCreate={createIp}
          />
          <main className="workspace-main" aria-labelledby="workspace-title">
            <div className="workspace-intro">
              <div>
                <p className="eyebrow">内容资产 · 版本管理</p>
                <h1 id="workspace-title">{selectedIp?.name ?? '开始管理你的 IP'}</h1>
                <p className="workspace-subtitle">
                  {selectedIp?.summary || '角色规范和素材版本都属于明确的 IP，不会混在一起。'}
                </p>
              </div>
              <div className="workspace-metadata">
                <span>工作室</span>
                <strong>{ips.length} 个 IP</strong>
              </div>
            </div>

            {error && <p className="inline-error" role="alert">{error}</p>}
            {selectedIp ? (
              <>
                <div className="workspace-tabs" role="tablist" aria-label="工作区">
                  <button
                    type="button"
                    role="tab"
                    aria-selected={view === 'assets'}
                    className={view === 'assets' ? 'is-active' : ''}
                    onClick={() => changeView('assets')}
                  >
                    素材库
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={view === 'bibles'}
                    className={view === 'bibles' ? 'is-active' : ''}
                    onClick={() => changeView('bibles')}
                  >
                    角色与画风
                  </button>
                  <button
                    type="button"
                    role="tab"
                    aria-selected={view === 'comics'}
                    className={view === 'comics' ? 'is-active' : ''}
                    onClick={() => changeView('comics')}
                  >
                    漫画工作台
                  </button>
                </div>
                {view === 'comics' ? (
                  <Suspense fallback={<section className="loading-workspace" role="status">正在打开漫画工作台…</section>}>
                    <ComicWorkspace key={selectedIp.id} ip={selectedIp} onDirtyChange={setComicWorkspaceDirty} />
                  </Suspense>
                ) : view === 'assets' ? (
                  <AssetLibrary
                    api={api}
                    ips={ips}
                    selectedIpId={selectedIp.id}
                    onSelectIp={changeSelectedIp}
                  />
                ) : (
                  <BibleEditor api={api} ip={selectedIp} onDefaultStyleSet={updateDefaultStyle} />
                )}
              </>
            ) : (
              <section className="first-ip-card">
                <span className="first-ip-mark" aria-hidden="true">＋</span>
                <div>
                  <p className="eyebrow">新的工作室</p>
                  <h2>从第一个 IP 开始</h2>
                  <p>先在左侧创建 IP，随后可以导入标准素材并建立角色、画风规范。</p>
                </div>
              </section>
            )}
          </main>
        </div>
      )}
    </div>
  );
}
