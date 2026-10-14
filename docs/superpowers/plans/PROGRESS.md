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

- [x] Task 2：Workspace / IP / Series / Episode 数据与 API
- [x] Task 3：安全上传 / Blob 去重 / AssetVersion
- [ ] Task 4：Character Bible 与 Style Bible 批准版本
- [ ] Task 5：多 IP 资产管理页面

#### Task 3 交付记录

- 提交：`feat(assets): add immutable safe image asset registry`
- RED 证据：初次运行 `uv run --project services/api pytest services/api/tests/test_assets.py -v` 在收集阶段因 `app.models.assets` 尚不存在而失败。
- 素材验证：该文件 13 passed；完整后端 `uv run --project services/api pytest -v`（19 passed）；前端 `pnpm --filter @ip-studio/web test`（1 passed）及 `pnpm --filter @ip-studio/web build` 成功。
- 迁移验证：SQLite 上升级到 head、`alembic check`（无新变更）、回滚到 base、再升级，全部通过。
- 结果：只接受并完整解码 PNG/JPEG/WebP；限制默认 25 MiB/40 MP；按 SHA-256 原子存 Blob 并去重；资产、版本和下载按所属 IP 检查；新版本保留旧版本；删除需显式确认且引用中的版本返回 409，Blob 最后一个版本删除后才清理。
- 环境限制：Docker daemon 仍未运行，且无本地 PostgreSQL，因此本任务未执行 PostgreSQL 运行时冒烟；数据库路径目前由 SQLite 测试和 Alembic 生命周期验证覆盖。

#### Task 2 交付记录

- 提交：`feat(domain): add scoped IP and story models`
- RED 证据：新增三个唯一性/隔离测试后，在模型与路由实现前运行 `pytest tests/test_ips.py -v`，重复 IP、重复分集和跨 workspace 访问均因路由未实现而失败（405）。
- GREEN 与回归：`uv run --project services/api pytest -v`（6 passed）；`uv sync --project services/api --locked --group dev`。
- 数据迁移：SQLite 上执行 Alembic upgrade、`alembic check`（无新变更）、downgrade base、再次 upgrade，全部通过。
- 结果：建立单管理员 workspace、IP/Series/Episode 模型与迁移、workspace-scoped CRUD、JWT 登录及密码哈希；不同 workspace 的资源通过服务查询隔离，复合外键约束归属。
- 环境限制：本机 Docker daemon 未运行，且没有本地 PostgreSQL 二进制，因此本任务无法做 PostgreSQL 容器运行时冒烟；使用 SQLite 跑 API 测试和迁移生命周期验证。Task 1 的 Compose 配置检查已通过。

## 阶段 02：品牌模板与画布

- [ ] Task 1–5：见 `2026-10-14-02-brand-templates-and-canvas.md`

## 阶段 03：剧本分镜与生产

- [ ] Task 1–4：见 `2026-10-14-03-storyboard-and-production.md`

## 阶段 04：Codex ImageGen 集成

- [ ] Task 1–4：见 `2026-10-14-04-codex-imagegen-integration.md`

## 阶段 05：导出与验收

- [ ] Task 1–5：见 `2026-10-14-05-export-and-acceptance.md`
