# IP Studio V1 实施进度

> 以 `docs/superpowers/plans/README.md` 中的正式顺序执行。日期使用 Asia/Shanghai。

## 阶段 01：工程基础与资产版本

### Task 1：工程底座与健康检查 — 已完成

- 提交：`chore: bootstrap V1 web API and test harness`
- RED 证据：`uv run --project services/api pytest services/api/tests/test_health.py -v` 返回预期 404；`pnpm --dir apps/web exec vitest run src/App.test.tsx` 因缺少可访问的 IP Studio 标题失败。
- GREEN 与构建：`pnpm --filter @ip-studio/web test`（1 passed）；`pnpm --filter @ip-studio/web build`；`uv run --project services/api pytest -v`（1 passed）。
- 工程验证：`pnpm install --frozen-lockfile --registry=https://registry.npmjs.org`；`uv sync --project services/api --locked --group dev`；`docker compose config -q`；`git diff --check`。
- 结果：React/Vite 工作区、FastAPI 健康端点、PostgreSQL Compose、环境变量示例和基础 CI 已建立。
- 边界：Compose 文件已校验，但本任务没有启动数据库容器；业务模型与 CRUD 属于后续任务。

### 后续任务

- [ ] Task 2：Workspace / IP / Series / Episode 数据与 API
- [ ] Task 3：安全上传 / Blob 去重 / AssetVersion
- [ ] Task 4：Character Bible 与 Style Bible 批准版本
- [ ] Task 5：多 IP 资产管理页面

## 阶段 02：品牌模板与画布

- [ ] Task 1–5：见 `2026-10-14-02-brand-templates-and-canvas.md`

## 阶段 03：剧本分镜与生产

- [ ] Task 1–4：见 `2026-10-14-03-storyboard-and-production.md`

## 阶段 04：Codex ImageGen 集成

- [ ] Task 1–4：见 `2026-10-14-04-codex-imagegen-integration.md`

## 阶段 05：导出与验收

- [ ] Task 1–5：见 `2026-10-14-05-export-and-acceptance.md`
