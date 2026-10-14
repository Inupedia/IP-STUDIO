export default function App() {
  return (
    <div className="app-shell">
      <header className="topbar">
        <a className="wordmark" href="/" aria-label="IP Studio 首页">
          <span className="wordmark-mark" aria-hidden="true">IP</span>
          <span>STUDIO</span>
        </a>
        <span className="topbar-context">原创 IP 创作工作台</span>
      </header>

      <main className="workspace" aria-labelledby="workspace-title">
        <section className="welcome-panel">
          <p className="eyebrow">数字资产 · 漫画创作</p>
          <h1 id="workspace-title">IP Studio</h1>
          <p className="welcome-copy">管理原创 IP、角色资产与漫画作品。</p>
        </section>

        <section className="empty-state" aria-labelledby="empty-state-title">
          <div className="empty-state-rule" aria-hidden="true" />
          <div>
            <p className="eyebrow">工作台</p>
            <h2 id="empty-state-title">从一个 IP 开始</h2>
            <p>创建 IP 后，可以在这里维护角色与画风版本、管理素材，并继续制作漫画。</p>
          </div>
        </section>
      </main>
    </div>
  );
}
