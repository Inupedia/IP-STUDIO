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

- [ ] **Step 1: Write the failing test** — `test_missing_codex_reports_unavailable / test_skill_present_but_imagegen_unavailable`；不能从 Skill 安装情况推断 imagegen 已可用；失败有错误原因且无假任务进度
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_codex_capabilities.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 探测 Codex 可执行文件、当前认证及工具暴露情况；设计显式 E2E Probe（只在用户主动触发时消耗额度）；记录本机 CLI/App Server 实际版本及结果到能力矩阵，禁止硬编码肯定支持
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_codex_capabilities.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/codex services/api/app/api/codex.py services/api/tests/test_codex_capabilities.py docs/architecture/codex-capability-matrix.md && git commit -m "feat(codex): probe real local imagegen capabilities"`.


### Task 2: 本地任务 Adapter 与图片安全回流

**Files:**
- Create: `services/api/app/codex/adapter.py; services/api/app/codex/image_result.py`
- Create: `services/api/app/api/codex_runs.py; apps/web/src/features/codex/CodexStatus.tsx`
- Test: `services/api/tests/test_codex_runs.py`

**Interfaces:**
- Consumes: 能力 PoC、GenerationTask 与 Phase 01 AssetStore
- Produces: `generate_image(task_id: UUID, inputs: GenerationInputs) -> GenerationCandidate`；`validate_image_result(path: Path, allowed_dir: Path) -> ValidatedImage`

- [ ] **Step 1: Write the failing test** — `test_valid_png_candidate_import / test_no_output_is_failure / test_path_escape_rejected`；仅在能力确认后执行；生成无字图落入专属 job 目录，PNG/JPEG 魔数/像素合法，候选入库需审阅
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_codex_runs.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 以 App Server/CLI 实际可用路径建立进程适配、事件日志、超时/取消、临时目录和安全文件结果校验；状态 queued/running/candidate_ready/failed
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_codex_runs.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/codex services/api/app/api/codex_runs.py apps/web/src/features/codex services/api/tests/test_codex_runs.py && git commit -m "feat(codex): execute gated imagegen and import candidates"`.


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

