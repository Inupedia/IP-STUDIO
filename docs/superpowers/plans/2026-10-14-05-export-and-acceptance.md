# 05 — Export, Portability and Release Acceptance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 导出可用于小红书的 PNG 图组、可完整恢复的工程 ZIP 与元素级可编辑 PPTX，并通过 EP01/EP02 全链路验收。

**Architecture:** 先根据冻结的 BrandTemplateVersion 和 CanvasDocument 渲染每页，再导出；ZIP 以 manifest/hash 验证所有引用；PPTX 逐层写成原生图形/文本/图片而不是整页截图。验收脱离付费 AI API。

**Tech Stack:** Konva, PptxGenJS, Python zipfile/Pillow, React, FastAPI, Playwright, pytest, Vitest

**Spec:** `docs/product/PRD-v1.md`; `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`

## Global Constraints

- 单管理员、多 IP；从请求到文件路径均校验 workspace / ip 归属。
- 角色、画风、品牌、资产批准版不可覆盖；画布工程 `schema_version = "1.0"`，默认 1080×1440 px。
- IP 品牌外壳固定，仅标题**文本**和剧情/分镜动态；ImageGen 只生成无字位图；中文消息独立渲染。
- Codex 生图仅在实际能力探测通过时启用；在线 ChatGPT 人工生图/导入必须一直可用；不使用私人端点/Cookie/隐式付费 API。
- 每个 Task 必须 RED → GREEN → Commit，确保提交真实测试与验收证据。

## Review Focus

- PNG 页面在导出时丢失中文或部分气泡 → 阻断（Task 1）
- 工程 ZIP 缺某个 AssetVersion 或路径穿越 → 拒绝导入（Task 2）
- PPTX 每页只有一张整页 PNG → 测试必须失败（Task 3）
- 相同模板 EP01/02 外层底色与 Logo 改变 → E2E 失败（Task 4）
- Codex 不可用时生成入口失效或无法交付 → E2E 失败（Task 4）

---

### Task 1: 原尺寸 PNG 多页导出

**Files:**
- Create: `apps/web/src/features/export/exportPng.ts; apps/web/src/features/export/ExportPanel.tsx`
- Create: `services/api/app/models/exports.py; services/api/app/api/exports.py`
- Test: `apps/web/src/features/export/exportPng.test.ts; services/api/tests/test_exports.py`

**Interfaces:**
- Consumes: BrandTemplateVersion + CanvasDocumentV1 + blob 加载器
- Produces: `renderPageToPng(doc: CanvasDocumentV1, pageId: string): Promise<Blob>`; POST /api/v1/episodes/{id}/export 绑定 revision

- [ ] **Step 1: Write the failing test** — `test_png_correct_dimensions_and_brand_shell / test_export_revision_immutable`；1080×1440 原始尺寸，无画布参考线，文字清晰且变更后导出绑定新 revision
- [ ] **Step 2: Verify RED** — Run `pnpm --dir apps/web exec vitest run src/features/export/exportPng.test.ts && cd services/api && uv run pytest tests/test_exports.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 在当前画布场景按 document 尺寸渲染；逐页命名有序，出错不产生完成状态；入库导出工件和警告
- [ ] **Step 4: Verify GREEN** — Run `pnpm --dir apps/web exec vitest run src/features/export/exportPng.test.ts && cd services/api && uv run pytest tests/test_exports.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add apps/web/src/features/export services/api/app/models/exports.py services/api/app/api/exports.py services/api/tests/test_exports.py && git commit -m "feat(export): generate PNG manga pages"`.


### Task 2: 工程 ZIP 备份/恢复与完整性校验

**Files:**
- Create: `services/api/app/export/project_bundle.py; services/api/app/api/project_import.py`
- Create: `packages/contracts/src/project-manifest.ts`
- Test: `services/api/tests/test_project_bundle.py`

**Interfaces:**
- Consumes: DocumentRevision 与所有引用的 AssetVersion/Blob
- Produces: `export_project_bundle(episode_id: UUID, revision: int) -> bytes`; `import_project_bundle(payload: bytes) -> ImportResult`；manifest 保存 schema_version 与 blobs sha256

- [ ] **Step 1: Write the failing test** — `test_zip_roundtrip_preserves_layers / test_missing_blob_rejected / test_zip_slip_rejected`；完整重导后标题/图层/版本引用不变；禁止 ../、绝对路径、符号链接和超尺寸 ZIP bomb
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_project_bundle.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — ZIP manifest + JSON 文档 + 引用原图与校验 hash，导入使用临时目录和事务，验证通过才持久化
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_project_bundle.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/export services/api/app/api/project_import.py services/api/tests/test_project_bundle.py packages/contracts/src/project-manifest.ts && git commit -m "feat(export): add verifiable editable project zip"`.


### Task 3: 原生对象 PPTX 导出

**Files:**
- Create: `apps/web/src/features/export/exportPptx.ts; apps/web/src/features/export/pptxMapper.ts`
- Test: `apps/web/src/features/export/pptxMapper.test.ts; apps/web/src/features/export/exportPptx.test.ts`

**Interfaces:**
- Consumes: CanvasDocumentV1 + 品牌外壳 + 独立 image/text/shape/chat 元素
- Produces: `mapCanvasElementToPptx(element: CanvasElement, context: PptxContext): PptxObject[]`; `exportEpisodePptx(doc: CanvasDocumentV1): Promise<Blob>`

- [ ] **Step 1: Write the failing test** — `test_pptx_contains_text_and_multiple_picture_shapes`；用 jszip/PPTX XML 检查存在独立文本框和多图片/形状节点，不能仅整页一个 raster
- [ ] **Step 2: Verify RED** — Run `pnpm --dir apps/web exec vitest run src/features/export/pptxMapper.test.ts src/features/export/exportPptx.test.ts`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — PptxGenJS 为每页建纵向 slide，独立生成文字、气泡背景/尾巴、聊天组件、角色图片；复杂裁切或字体不等价时 warnings[] 告警
- [ ] **Step 4: Verify GREEN** — Run `pnpm --dir apps/web exec vitest run src/features/export/pptxMapper.test.ts src/features/export/exportPptx.test.ts`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add apps/web/src/features/export && git commit -m "feat(export): create element-editable pptx manga"`.


### Task 4: EP01 / EP02 回归和 AC-01～AC-26 验收

**Files:**
- Create: `tests/e2e/ip-studio.spec.ts; tests/e2e/fixtures/ip-studio-seed.json`
- Create: `docs/qa/V1-acceptance-matrix.md; docs/qa/V1-manual-runbook.md`
- Test: `services/api/tests/test_acceptance_smoke.py`

**Interfaces:**
- Consumes: 所有已合并阶段 01–04；能创建真实 demo IP 与可再分发素材 fixture
- Produces: `tests/e2e/ip-studio.spec.ts` 端到端流程；验收矩阵每项链接自动化或人工证据

- [ ] **Step 1: Write the failing test** — `ep01_chat_direction_and_ep02_shared_brand_are_stable / generation_fallback_works`；EP01 左‘在吗？’右‘不在。’、模板一致、替换单格/改对白不改其它格、导出可打开
- [ ] **Step 2: Verify RED** — Run `pnpm --dir apps/web exec playwright test tests/e2e/ip-studio.spec.ts && cd services/api && uv run pytest tests/test_acceptance_smoke.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 使用可共享占位素材搭建两期案例，跑浏览器及回读测试；逐条列 AC-01～AC-26 的 PASS/FAIL/BLOCKED 和可重现步骤；绝不虚报图片 API 测试
- [ ] **Step 4: Verify GREEN** — Run `pnpm --dir apps/web exec playwright test tests/e2e/ip-studio.spec.ts && cd services/api && uv run pytest tests/test_acceptance_smoke.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add tests/e2e docs/qa services/api/tests/test_acceptance_smoke.py && git commit -m "test(e2e): verify IP Studio V1 scenarios"`.


### Task 5: 本地部署、备份/恢复与交接审核

**Files:**
- Create: `docs/deployment/local-development.md; docs/deployment/backup-restore.md`
- Create: `scripts/verify-v1.sh; .github/workflows/ci.yml`
- Test: `docs/qa/V1-release-checklist.md`

**Interfaces:**
- Consumes: 所有功能与 AC 验收报告
- Produces: `scripts/verify-v1.sh` 统一执行可用的后端、前端和 E2E 测试，并返回准确 exit status；真实备份恢复说明

- [ ] **Step 1: Write the failing test** — `verify-v1.sh exits_nonzero_when_backend_test_fails`；失败退出码非 0；备份数据库和资产及恢复可复演；最终发布无 fail 的阻断项
- [ ] **Step 2: Verify RED** — Run `bash scripts/verify-v1.sh`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 整理安装、环境变量、DB/Blob 备份恢复演练和失败排查；跑完整测试，把真实结果附到 release checklist。不得将未开发阶段标记完成
- [ ] **Step 4: Verify GREEN** — Run `bash scripts/verify-v1.sh`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add docs/deployment docs/qa/V1-release-checklist.md scripts/verify-v1.sh .github/workflows/ci.yml && git commit -m "docs(release): provide V1 verification and recovery runbooks"`.

