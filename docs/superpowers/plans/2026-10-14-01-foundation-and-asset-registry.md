# 01 — Foundation and Asset Registry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立可运行的 IP Studio mono-repo、多 IP 数据隔离、安全素材存储与角色/画风锁定版本。

**Architecture:** 从 FastAPI 与 React 工程出发建立后端数据库及 typed API；Blob 使用 SHA256 内容寻址，IP、角色、画风与引用使用不可变版本。

**Tech Stack:** React, TS, Vite, pnpm, Vitest, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pillow, pytest

**Spec:** `docs/product/PRD-v1.md`; `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`

## Global Constraints

- 单工作室管理员、多 IP；所有读写校验 workspace/ip 归属，网络 JSON 使用 snake_case。
- 批准后的角色、风格、素材、品牌版本不可覆写；工程有独立 `schema_version = "1.0"`。
- 品牌外壳锁定，标题文字和剧情动态；聊天气泡及中文为独立可编辑对象。
- 不能把 ChatGPT Plus 当作开发者 API；Codex ImageGen 只有真实自检通过后才启用。
- 先写失败测试再最小实现、测试通过后提交；不能将计划任务假报为已实现。

## Review Focus

- 文件名伪造的可执行内容 → MIME 魔数校验拒绝（Task 3）
- 相同二进制但不同名称 → 只保存一个 Blob（Task 3）
- 不同 IP 访问私有角色/素材 → 403/404（Task 2/3）
- 已批准 CharacterVersion 再编辑 → 409（Task 4）
- 系列分集编号重复 → 唯一索引拒绝（Task 2）

---

### Task 1: 工程底座与健康检查

**Files:**
- Create: `package.json; pnpm-workspace.yaml; apps/web/package.json; apps/web/src/App.tsx; apps/web/vite.config.ts`
- Create: `services/api/pyproject.toml; services/api/app/main.py; compose.yaml; .env.example; .github/workflows/ci.yml`
- Test: `services/api/tests/test_health.py; apps/web/src/App.test.tsx`

**Interfaces:**
- Consumes: 空仓库；README、PRD、设计文件
- Produces: `create_app() -> FastAPI`; GET /api/v1/health -> 200 {status:'ok'}; React 页面显示 IP Studio

- [x] **Step 1: Write the failing test** — `test_health_ok / App.test.tsx`: TestClient 对健康检查断言 200+status ok；React 检查页面标题存在
- [x] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_health.py -v && cd ../../ && pnpm --dir apps/web exec vitest run`; expected **FAIL** because the behavior has not been implemented.
- [x] **Step 3: Implement the minimal behavior** — 配置 pnpm/Vite/React、FastAPI/TestClient、PostgreSQL Compose、基础 CI；确保测试命令真实可运行
- [x] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_health.py -v && cd ../../ && pnpm --dir apps/web exec vitest run`; expected **PASS**. Run neighboring regression tests.
- [x] **Step 5: Commit** — `git add package.json pnpm-workspace.yaml apps/web services/api compose.yaml .env.example .github/workflows && git commit -m "chore: bootstrap V1 web API and test harness"`.


### Task 2: Workspace / IP / Series / Episode 数据与 API

**Files:**
- Create: `services/api/app/models/ip.py; services/api/app/models/story.py`
- Create: `services/api/app/services/ips.py; services/api/app/api/ips.py; services/api/alembic/versions/0001_ip_story.py`
- Test: `services/api/tests/test_ips.py`

**Interfaces:**
- Consumes: create_app() 与 DB Session；JWT/单管理员隔离可先使用 test auth stub，正式密码认证纳入本任务
- Produces: `create_ip(workspace_id: UUID, code: str, name: str) -> IP`；GET/POST /api/v1/ips；`create_episode(series_id: UUID, number: int, title: str) -> Episode`

- [x] **Step 1: Write the failing test** — `test_duplicate_ip_code_rejected / test_episode_number_unique / test_other_workspace_not_visible`: (workspace,code) 与 (series,number) 唯一；跨 workspace 不可读取
- [x] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_ips.py -v`; 缺少路由时重复资源请求返回 405，预期断言失败。
- [x] **Step 3: Implement the minimal behavior** — SQLAlchemy 模型、Alembic 迁移、服务层、scope validation、JWT 单管理员认证与 IP/Series/Episode CRUD。
- [x] **Step 4: Run test to verify GREEN** — `uv run --project services/api pytest -v`；6 passed。SQLite Alembic upgrade/check/downgrade/upgrade 均通过。
- [x] **Step 5: Commit** — `feat(domain): add scoped IP and story models`。


### Task 3: 安全上传 / Blob 去重 / AssetVersion

**Files:**
- Create: `services/api/app/models/assets.py; services/api/app/storage/local_blobs.py`
- Create: `services/api/app/services/assets.py; services/api/app/api/assets.py; services/api/alembic/versions/0002_assets.py`
- Test: `services/api/tests/test_assets.py`

**Interfaces:**
- Consumes: IP/workspace 归属与 DB Session
- Produces: `put_blob(data: bytes, mime: str) -> StoredBlob`; `create_asset_version(workspace_id: UUID, asset_id: UUID, blob_id: UUID) -> AssetVersion`; POST /api/v1/assets/upload

- [x] **Step 1: Write the failing test** — 覆盖伪造/超大/MIME 不匹配/像素超限、PNG/JPEG/WebP、SHA 去重、跨 IP 隔离、版本读取与删除保护。
- [x] **Step 2: Run the test to verify RED** — `uv run --project services/api pytest services/api/tests/test_assets.py -v`；实现前因 `app.models.assets` 不存在而收集失败。
- [x] **Step 3: Implement the minimal behavior** — SHA-256 内容寻址 Blob、PNG/JPEG/WebP 解码、原子写入、IP-scoped 上传/读取/版本/删除以及引用保护。
- [x] **Step 4: Run test to verify GREEN** — 素材测试 13 passed；完整后端测试 19 passed；前端 Vitest 1 passed、Vite build 成功。Alembic upgrade/check/downgrade/upgrade 通过。
- [x] **Step 5: Commit** — `feat(assets): add immutable safe image asset registry`。


### Task 4: Character Bible 与 Style Bible 批准版本

**Files:**
- Create: `services/api/app/models/bibles.py; services/api/app/schemas/bibles.py`
- Create: `services/api/app/services/bibles.py; services/api/app/api/bibles.py; services/api/alembic/versions/0003_bibles.py`
- Test: `services/api/tests/test_bibles.py`

**Interfaces:**
- Consumes: AssetVersion 与 IP
- Produces: `create_character_candidate(character_id: UUID, bible: dict) -> CharacterVersion`; `approve_character_version(version_id: UUID) -> CharacterVersion`; Style 对应能力

- [x] **Step 1: Write the failing test** — 已批准版保留原 payload 并可派生候选；角色/画风引用需为同 IP 已批准素材；默认画风需为同 IP 已批准版本。
- [x] **Step 2: Run the test to verify RED** — `uv run --project services/api pytest services/api/tests/test_bibles.py -v`；4 项因 Character/Style API 未实现返回 404。
- [x] **Step 3: Implement the minimal behavior** — Character/Style JSON Bible、追加式版本和审批审计、AssetVersion 审批与引用授权、IP 默认画风。
- [x] **Step 4: Run test to verify GREEN** — 专项测试 4 passed；完整后端 23 passed；前端 Vitest 1 passed、Vite build 成功。SQLite Alembic upgrade/check/downgrade/upgrade 均通过。
- [x] **Step 5: Commit** — `feat(ip): introduce immutable character and style bibles`。


### Task 5: 多 IP 资产管理页面

**Files:**
- Create: `apps/web/src/features/ips/IpList.tsx; apps/web/src/features/assets/AssetLibrary.tsx`
- Create: `apps/web/src/features/bibles/BibleEditor.tsx; apps/web/src/lib/api.ts; packages/contracts/src/domain.ts`
- Test: `apps/web/src/features/assets/AssetLibrary.test.tsx`

**Interfaces:**
- Consumes: 后端 IP/Asset/Bible 接口
- Produces: `getIps(): Promise<IP[]>`; `uploadAsset(file: File, ipId: string): Promise<AssetVersion>`；可切换 IP 过滤资产与管理 Bible

- [x] **Step 1: Write the failing test** — `AssetLibrary.test.tsx: filters_are_scoped_by_ip`: 切换 IP 后不展示其他 IP 私有资产；候选批准状态符合响应，并将正确 IP/Asset/Version 传入审批请求
- [x] **Step 2: Run the test to verify RED** — 初次运行因 `AssetLibrary` 尚不存在而导入失败；实现后修正断言范围，避免筛选器的“候选”选项造成歧义。
- [x] **Step 3: Implement the minimal behavior** — 建立 typed fetch、IP 工作区、资产上传/筛选/审批/预览、角色与画风完整 Bible 编辑、不可变版本审批和派生、同 IP 已批准素材引用及默认画风设置
- [x] **Step 4: Run test to verify GREEN** — `pnpm --filter @ip-studio/web test`（2 passed）；`pnpm --filter @ip-studio/web build` 成功；完整后端 `uv run --project services/api pytest -v`（23 passed）；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(ui): implement IP asset and bible workspace`。

