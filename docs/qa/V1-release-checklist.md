# IP Studio V1 发布检查表

## 验证结果（2026-10-14）

- [x] 前端 Vitest：26 个文件，73 项通过。
- [x] Playwright Chromium：16 条端到端流程通过，含 EP01/EP02、ChatGPT Web 手动回退、两个标签页 CAS、保存时继续编辑、异步创建期间锁定工作台、画布真实组拖动、10 页 PNG 与 30 图层回归。
- [x] FastAPI pytest：95 项通过；API 测试数据库为临时 SQLite。
- [x] Vite/TypeScript production build 通过；工作台/导出功能按需拆分加载。
- [x] PR head `7bde8b0` 的完整本地 `bash scripts/verify-v1.sh`（FastAPI 95、Vitest 73、Playwright Chromium 16、production build）通过，终端日志已保存：[verify-v1-7bde8b0.log](evidence/verify-v1-7bde8b0.log)。
- [x] PNG ZIP 浏览器路径检查 10 张实际渲染页的 1080×1440 尺寸与页序。
- [x] PPTX 浏览器 XML 验收含多个独立图片/形状/中文文本对象；阶段 Task 3 使用 LibreOffice 打开/转换通过。
- [x] `scripts/verify-v1.sh` 首个后端步骤失败时保留原始非零退出码（故障注入验证退出码 `37`）。
- [x] 保存 EP02 Playwright 验收截图：[evidence/ep02-editor.png](evidence/ep02-editor.png)。
- [x] PostgreSQL 17.11 runtime migration upgrade/check/downgrade/upgrade/check，以及真实数据库 + Blob 联合恢复；管理员登录、图片读取和工程 ZIP 重导出均通过，见 AC-18。
- [x] GitHub Actions 的 PostgreSQL 17 migration、API 与 Playwright web jobs 已在当前提交通过：[push run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38571567297)、[PR run](https://github.com/Inupedia/IP-STUDIO/actions/runs/38571574764)；GitGuardian Security Checks 通过。
- [ ] API-owned Codex 原生 ImageGen 探测与候选回流：Homebrew 稳定 CLI 与桌面包内 CLI 均未通过管理员 probe；后者超时，见 AC-25 和[运行时探测证据](evidence/codex-bundled-runtime-probe-2026-10-15.json)。OpenAI 当前 ChatGPT-plan App Server 文档将 Image Generation 列为不支持；在合规兼容运行时通过同一 E2E 门禁前不得勾选。

## 阻断规则

- [ ] 发布前 [V1-acceptance-matrix.md](V1-acceptance-matrix.md) 中没有 `BLOCKED` 项。
- [x] 用真实 PostgreSQL 数据库与 `ASSET_STORAGE_DIR` Blob 目录执行一次备份/恢复，并确认登录、图片预览、工程 ZIP 再导出。
- [ ] 从管理员界面显式运行 Codex ImageGen 能力探测，再启动任务；核实真实 PNG 自动成为 `pending_review` 候选，未经批准不得进入正式画布。
- [ ] 对发布版本运行 `bash scripts/verify-v1.sh` 并保存终端日志。
- [ ] 生产配置不使用 `.env.example` 中的本地测试密码；设置强 JWT secret、HTTPS 反向代理、防火墙和外部备份存储。

**当前结论：V1 功能代码、本地自动化回归和 PostgreSQL/Blob 恢复演练已完成；发布门槛仍未全部满足。AC-25 是唯一 `BLOCKED` 验收项，远端 GitHub Actions、发布版本验证日志及生产配置检查仍待完成。**
