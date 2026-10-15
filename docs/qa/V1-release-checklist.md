# IP Studio V1 发布检查表

## 验证结果（2026-10-15）

- [x] 前端 Vitest：26 个文件，73 项通过。
- [x] Playwright Chromium：16 条端到端流程通过，含 EP01/EP02、ChatGPT Web 手动回退、两个标签页 CAS、保存时继续编辑、异步创建期间锁定工作台、画布真实组拖动、10 页 PNG 与 30 图层回归。
- [x] FastAPI pytest：95 项通过；API 测试数据库为临时 SQLite。
- [x] Vite/TypeScript production build 通过；工作台/导出功能按需拆分加载。
- [x] PR head `7bde8b0` 的完整本地 `bash scripts/verify-v1.sh`（FastAPI 95、Vitest 73、Playwright Chromium 16、production build）通过，终端日志已保存：[verify-v1-7bde8b0.log](evidence/verify-v1-7bde8b0.log)。
- [x] 当前 PR snapshot `3cff5e3` 的完整本地 `bash scripts/verify-v1.sh` 通过：FastAPI 98、Vitest 73、Playwright Chromium 16、production build；日志：[verify-v1-3cff5e3.log](evidence/verify-v1-3cff5e3.log)。这是 PR 源码验证，不能替代版本化发布制品验证。
- [x] 当前 AC-25 App Server readback 与 thread 清理变更的完整本地 `bash scripts/verify-v1.sh` 通过：FastAPI 104、Vitest 73、Playwright Chromium 16、production build；日志：[verify-v1-ac25-app-server-readback-2026-10-15.log](evidence/verify-v1-ac25-app-server-readback-2026-10-15.log)。远端 CI 需在本轮 commit 推送后重新运行。
- [x] PNG ZIP 浏览器路径检查 10 张实际渲染页的 1080×1440 尺寸与页序。
- [x] PPTX 浏览器 XML 验收含多个独立图片/形状/中文文本对象；阶段 Task 3 使用 LibreOffice 打开/转换通过。
- [x] `scripts/verify-v1.sh` 首个后端步骤失败时保留原始非零退出码（故障注入验证退出码 `37`）。
- [x] 保存 EP02 Playwright 验收截图：[evidence/ep02-editor.png](evidence/ep02-editor.png)。
- [x] PostgreSQL 17.11 runtime migration upgrade/check/downgrade/upgrade/check，以及真实数据库 + Blob 联合恢复；管理员登录、图片读取和工程 ZIP 重导出均通过，见 AC-18。
- [x] GitHub Actions 的 PostgreSQL 17 migration、API 与 Playwright web jobs 在提交 `3cff5e3` 通过：[push run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38668483943)、[PR run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38668487628)；GitGuardian Security Checks 通过。
- [x] AC-25 readback implementation head `bc816e8` 的 push 与 PR GitHub Actions API/Web jobs 全部通过，GitGuardian Security Checks 通过：[push run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38676878705)、[PR run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38676883485)。后续 docs head `0ac1a95` 的检查也通过；thread 清理修正待提交后重跑 CI。独立 PR review 尚待完成。
- [x] thread 失败清理修正 head `d175dfb` 的 push 与 PR GitHub Actions API/Web jobs 全部通过，GitGuardian Security Checks 通过：[push run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38680690391)、[PR run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38680695596)。独立 PR review 尚待完成。
- [x] API-owned Codex 原生 ImageGen 探测与候选回流：Homebrew CLI `0.162.1` 通过管理员 probe；同一 API 实例的真实 Codex run 创建 `codex_native` 候选，状态先为 `pending_review`，经管理员批准后变为 `approved`。旧的桌面包 CLI 超时、Cursor CLI exit code `1` 仍未通过，但没有缓存为可用 runtime。完整脱敏证据见[AC-25 probe + 候选回流](evidence/ac25-native-imagegen-app-server-readback-2026-10-15.json)和[能力矩阵](../architecture/codex-capability-matrix.md)。

## 阻断规则

- [x] 发布前 [V1-acceptance-matrix.md](V1-acceptance-matrix.md) 中没有 `BLOCKED` 项；AC-01～AC-26 均为 `PASS`。
- [x] 用真实 PostgreSQL 数据库与 `ASSET_STORAGE_DIR` Blob 目录执行一次备份/恢复，并确认登录、图片预览、工程 ZIP 再导出。
- [x] 通过管理员保护的 API 显式运行 Codex ImageGen 能力探测，再启动任务；真实 PNG 自动成为 `pending_review` 候选，经管理员批准后方可复用。完整服务端回流见 AC-25 证据。
- [ ] 创建明确的 V1 发布版本/制品后，对该版本运行 `bash scripts/verify-v1.sh` 并保存终端日志；PR snapshot 验证见上方，尚不代表发布版本。
- [ ] 在选定的实际生产主机配置并核验强 JWT secret、专用数据库凭据、生产 Web origins、HTTPS 反向代理、防火墙和外部备份存储。当前仓库没有生产主机/域名或部署目标，因此本项未执行。

**当前结论：AC-01～AC-26 均通过；本轮完整本地验证、thread 清理修正 head 的 push/PR CI 与 GitGuardian 均通过，独立 PR review 尚待完成。版本化发布验证和实际生产环境配置仍待执行。**
