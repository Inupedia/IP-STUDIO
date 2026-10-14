# 04 — Local Codex and ImageGen Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 经真实环境探测有条件地接入本机 Codex ImageGen、自动入库，并让 Codex 在审查后修改结构化漫画工程。

**Architecture:** 创建受限 Codex Adapter / 本地 Bridge；能力探测是独立 PoC Gate，必须验证真实图片产物。生成失败总是降级到已经完成的人工任务卡；对文档的更改只有通过 Patch Validator + 用户批准才能提交。

**Tech Stack:** Python FastAPI, Codex App Server/CLI (if available), SSE, Pydantic, pytest, Playwright

**Spec:** `docs/product/PRD-v1.md`; `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`

## Global Constraints

- 单管理员、多 IP；从请求到文件路径均校验 workspace / ip 归属。
- 角色、画风、品牌、资产批准版不可覆盖；画布工程 `schema_version = "1.0"`，默认 1080×1440 px。
- IP 品牌外壳固定，仅标题**文本**和剧情/分镜动态；ImageGen 只生成无字位图；中文消息独立渲染。
- Codex 生图仅在实际能力探测通过时启用；在线 ChatGPT 人工生图/导入必须一直可用；不使用私人端点/Cookie/隐式付费 API。
- 每个 Task 必须 RED → GREEN → Commit，确保提交真实测试与验收证据。

## Review Focus

- Codex CLI/内置 ImageGen 缺失 → capability=unavailable 和人工回退（Task 1）
- CLI/工具存在但生成未产出有效 PNG → failed 不入库（Task 2）
- Codex 产生恶意相对路径或超出 workspace 输出路径 → 拒绝（Task 2）
- Codex 尝试修改锁定 BrandTemplate/其他 IP → Patch validator 拒绝（Task 3）
- base_revision 过时或用户拒绝建议 → 无数据库更改（Task 4）

---

### Task 1: Codex 环境能力自检 PoC

**Files:**
- Create: `services/api/app/codex/capabilities.py; services/api/app/api/codex.py`
- Create: `docs/architecture/codex-capability-matrix.md`
- Test: `services/api/tests/test_codex_capabilities.py`

**Interfaces:**
- Consumes: 本地 Codex（如安装），Phase 03 手工生成入口
- Produces: `probe_capabilities() -> CapabilityReport`；GET /api/v1/codex/capabilities -> `available/unavailable/needs_auth/unsupported` + reason；真实 probe 需验证可生成解码图片

- [x] **Step 1: Write the failing test** — 覆盖 CLI 缺失、未登录、provider 未暴露 ImageGen、仅声明能力不可直接标可用、API GET 不触发生图、显式 probe 必须有原生 ImageGen 事件及可解码 PNG。
- [x] **Step 2: Verify RED** — 功能模块尚不存在时测试因 `app.codex` 缺失而失败；显式 probe API 实现前对应测试因缺少路由/调用器而失败，均为预期功能缺失。
- [x] **Step 3: Implement minimally** — 使用 `codex login status` 和公开 App Server `modelProvider/capabilities/read`；GET 只读且不消耗生成额度，管理员 POST 才会启动临时、受限、可超时的 ImageGen E2E probe。要求事件记录中出现原生 ImageGen 调用、路径处于探测目录、PNG 魔数/解码/尺寸/大小均有效；仅缓存通过的 CLI 路径与版本。记录当前环境实际 CLI/App Server/ImageGen 证据及瞬时网络限制。
- [x] **Step 4: Verify GREEN** — 能力专项后端 9 passed；完整后端 `uv run --project services/api pytest -q`（58 passed）；现场只读 probe 实测 Codex CLI `0.162.1`、登录有效、App Server `imageGeneration=true`；一次真实 CLI ImageGen 产物经 Pillow 校验为有效 `1254×1254` PNG；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(codex): probe real local imagegen capabilities`。


### Task 2: 本地任务 Adapter 与图片安全回流

**Files:**
- Create: `services/api/app/codex/adapter.py; services/api/app/codex/image_result.py`
- Create: `services/api/app/api/codex_runs.py; apps/web/src/features/codex/CodexStatus.tsx`
- Test: `services/api/tests/test_codex_runs.py`

**Interfaces:**
- Consumes: 能力 PoC、GenerationTask 与 Phase 01 AssetStore
- Produces: `generate_image(task_id: UUID, inputs: GenerationInputs) -> GenerationCandidate`；`validate_image_result(path: Path, allowed_dir: Path) -> ValidatedImage`

- [x] **Step 1: Write the failing test** — 覆盖有效 PNG 待审候选、无输出失败、输出目录越界拒绝、真实原生 ImageGen 事件门槛、运行取消和 Codex 不可用时人工回退。
- [x] **Step 2: Verify RED** — 测试先因 `app.codex.image_result` 和 `app.api.codex_runs` 缺失而按预期失败，没有依赖缺失导致的假 RED。
- [x] **Step 3: Implement minimally** — 使用本机 Codex CLI `exec --json --sandbox workspace-write`；只附加校验过的冻结参考包；限定 job 临时目录、PNG/JPEG 魔数与 Pillow 解码、像素/字节上限和成功原生 ImageGen 事件；支持超时、管理员取消与同任务并发锁。结果以 `codex_native` 来源入库并关联待审候选，不自动审批。
- [x] **Step 4: Verify GREEN** — 专项 API/Adapter `uv run --project services/api pytest services/api/tests/test_codex_runs.py -v`（6 passed）；完整后端（64 passed）；完整前端（42 passed）；Codex + Generation 合同（5 passed）；Vite/TypeScript build 成功；SQLite 0010 migration upgrade、`alembic check`、downgrade base、upgrade head；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(codex): execute gated imagegen and import candidates`。


### Task 3: 结构化 CanvasPatch 白名单与授权校验

**Files:**
- Create: `packages/contracts/src/canvas-patch.ts; services/api/app/codex/patches.py`
- Create: `services/api/app/services/patch_validator.py`
- Test: `services/api/tests/test_codex_patches.py; packages/contracts/src/canvas-patch.test.ts`

**Interfaces:**
- Consumes: CanvasDocumentV1、品牌锁定规则、IP/版本权限
- Produces: `propose_patch(document_id: UUID, instruction: str) -> CanvasPatch`; `validate_canvas_patch(patch: CanvasPatch, scope: Scope, current_revision: int) -> ValidatedPatch`

- [ ] **Step 1: Write the failing test** — `test_cross_ip_patch_denied / test_locked_logo_patch_denied / test_unknown_operation_denied`；仅 set_text/set_transform/replace_image_asset/insert_element/remove_element；拒绝任意 SQL、路径和执行命令
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_codex_patches.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 限制 Patch AST 类型、ID 所属与具体版本、属性值范围和 max operations；只返回待审批建议，不直接执行写入
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_codex_patches.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add packages/contracts/src/canvas-patch.ts packages/contracts/src/canvas-patch.test.ts services/api/app/codex/patches.py services/api/app/services/patch_validator.py services/api/tests/test_codex_patches.py && git commit -m "feat(codex): validate scoped proposed canvas patches"`.


### Task 4: 用户确认、应用 Patch 与降级体验

**Files:**
- Create: `services/api/app/services/patch_approval.py; services/api/app/api/codex_patches.py`
- Create: `apps/web/src/features/codex/CodexAssistant.tsx; apps/web/src/features/codex/PatchPreview.tsx`
- Test: `services/api/tests/test_codex_patch_approval.py; apps/web/src/features/codex/CodexAssistant.test.tsx`

**Interfaces:**
- Consumes: Phase 02 CAS 文档保存 + Task 3 ValidatedPatch
- Produces: `apply_approved_patch(patch_id: UUID, base_revision: int, approval_id: UUID) -> DocumentRevision`；UI 提交/拒绝 patch

- [ ] **Step 1: Write the failing test** — `test_rejected_patch_has_no_side_effects / test_stale_revision_returns_409 / fallback_action_visible`；审批前不写，拒绝后不变；冲突 409；Codex 不可用时手动导入入口常驻
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_codex_patch_approval.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/codex/CodexAssistant.test.tsx`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 建立 PatchPreview diff、Approve/Reject 审计、原子应用；UI 明确标注条件式生成和不可用原因
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_codex_patch_approval.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/codex/CodexAssistant.test.tsx`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/services/patch_approval.py services/api/app/api/codex_patches.py services/api/tests/test_codex_patch_approval.py apps/web/src/features/codex && git commit -m "feat(codex): approve scoped edits with reliable fallback"`.

