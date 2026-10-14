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

- [ ] **Step 1: Write the failing test** — `test_health_ok / App.test.tsx`: TestClient 对健康检查断言 200+status ok；React 检查页面标题存在
- [ ] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_health.py -v && cd ../../ && pnpm --dir apps/web exec vitest run`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 配置 pnpm/Vite/React、FastAPI/TestClient、PostgreSQL Compose、基础 CI；确保测试命令真实可运行
- [ ] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_health.py -v && cd ../../ && pnpm --dir apps/web exec vitest run`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add package.json pnpm-workspace.yaml apps/web services/api compose.yaml .env.example .github/workflows && git commit -m "chore: bootstrap V1 web API and test harness"`.


### Task 2: Workspace / IP / Series / Episode 数据与 API

**Files:**
- Create: `services/api/app/models/ip.py; services/api/app/models/story.py`
- Create: `services/api/app/services/ips.py; services/api/app/api/ips.py; services/api/alembic/versions/0001_ip_story.py`
- Test: `services/api/tests/test_ips.py`

**Interfaces:**
- Consumes: create_app() 与 DB Session；JWT/单管理员隔离可先使用 test auth stub，正式密码认证纳入本任务
- Produces: `create_ip(workspace_id: UUID, code: str, name: str) -> IP`；GET/POST /api/v1/ips；`create_episode(series_id: UUID, number: int, title: str) -> Episode`

- [ ] **Step 1: Write the failing test** — `test_duplicate_ip_code_rejected / test_episode_number_unique / test_other_workspace_not_visible`: (workspace,code) 与 (series,number) 唯一；跨 workspace 不可读取
- [ ] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_ips.py -v`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — SQLAlchemy 模型、Alembic 迁移、服务层、scope validation、基础认证与 CRUD；保证状态与 API 结构固定
- [ ] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_ips.py -v`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add services/api/app services/api/alembic services/api/tests/test_ips.py && git commit -m "feat(domain): add scoped IP and story models"`.


### Task 3: 安全上传 / Blob 去重 / AssetVersion

**Files:**
- Create: `services/api/app/models/assets.py; services/api/app/storage/local_blobs.py`
- Create: `services/api/app/services/assets.py; services/api/app/api/assets.py; services/api/alembic/versions/0002_assets.py`
- Test: `services/api/tests/test_assets.py`

**Interfaces:**
- Consumes: IP/workspace 归属与 DB Session
- Produces: `put_blob(data: bytes, mime: str) -> StoredBlob`; `create_asset_version(workspace_id: UUID, asset_id: UUID, blob_id: UUID) -> AssetVersion`; POST /api/v1/assets/upload

- [ ] **Step 1: Write the failing test** — `test_reject_fake_png / test_sha256_dedupe / test_cross_ip_denied / test_delete_used_asset_blocked`: 25MB/MIME/魔数/尺寸校验，SHA 一致时底层只一份；不允许删除被引用素材
- [ ] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_assets.py -v`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 以 hash 存 Blob，数据库引用 AssetVersion；解码真实图片；临时文件原子落盘，失败清理
- [ ] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_assets.py -v`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add services/api/app services/api/alembic services/api/tests/test_assets.py && git commit -m "feat(assets): add immutable safe image asset registry"`.


### Task 4: Character Bible 与 Style Bible 批准版本

**Files:**
- Create: `services/api/app/models/bibles.py; services/api/app/schemas/bibles.py`
- Create: `services/api/app/services/bibles.py; services/api/app/api/bibles.py; services/api/alembic/versions/0003_bibles.py`
- Test: `services/api/tests/test_bibles.py`

**Interfaces:**
- Consumes: AssetVersion 与 IP
- Produces: `create_character_candidate(character_id: UUID, bible: dict) -> CharacterVersion`; `approve_character_version(version_id: UUID) -> CharacterVersion`; Style 对应能力

- [ ] **Step 1: Write the failing test** — `test_approved_character_immutable / test_approved_style_immutable / test_unapproved_reference_rejected`: 已批准版不能覆盖，更新需要新 candidate；参考图必须存在且授权
- [ ] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_bibles.py -v`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 实现角色/画风载荷与审批状态，保存版本唯一约束、来源参考和审计
- [ ] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_bibles.py -v`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add services/api/app services/api/alembic services/api/tests/test_bibles.py && git commit -m "feat(ip): introduce immutable character and style bibles"`.


### Task 5: 多 IP 资产管理页面

**Files:**
- Create: `apps/web/src/features/ips/IpList.tsx; apps/web/src/features/assets/AssetLibrary.tsx`
- Create: `apps/web/src/features/bibles/BibleEditor.tsx; apps/web/src/lib/api.ts; packages/contracts/src/domain.ts`
- Test: `apps/web/src/features/assets/AssetLibrary.test.tsx`

**Interfaces:**
- Consumes: 后端 IP/Asset/Bible 接口
- Produces: `getIps(): Promise<IP[]>`; `uploadAsset(file: File, ipId: string): Promise<AssetVersion>`；可切换 IP 过滤资产与管理 Bible

- [ ] **Step 1: Write the failing test** — `AssetLibrary.test.tsx: filters_are_scoped_by_ip`: 切换 IP 后不展示其他 IP 私有资产；候选批准状态符合响应
- [ ] **Step 2: Run the test to verify RED** — `pnpm --dir apps/web exec vitest run src/features/assets/AssetLibrary.test.tsx`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 建立 typed fetch、IP 路由、资产上传与查找、角色风格详情和版本审批 UI
- [ ] **Step 4: Run test to verify GREEN** — `pnpm --dir apps/web exec vitest run src/features/assets/AssetLibrary.test.tsx`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add apps/web/src packages/contracts/src && git commit -m "feat(ui): implement IP asset and bible workspace"`.

