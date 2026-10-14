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

- [x] **Step 1: Write the failing test** — 覆盖原始页面尺寸、品牌版本传入、无缺失素材占位导出、多页顺序、ZIP 页序与精确 revision 绑定，以及页数/尺寸不匹配拒绝。
- [x] **Step 2: Verify RED** — 新 API 路由实现前返回 404；前端导出模块实现前测试因 `exportPng` 不存在而失败，均为预期功能缺失。
- [x] **Step 3: Implement minimally** — 复用 Konva 的品牌和画格图层逐页渲染原始尺寸 PNG，不渲染网格/安全区；验证素材加载、像素和尺寸；服务端按 revision 校验并生成有序 ZIP，保存 SHA-256 Blob 与导出记录。
- [x] **Step 4: Verify GREEN** — 导出 API 专项 3 passed；完整后端 `uv run --project services/api pytest -q`（80 passed）；完整前端 `pnpm --filter @ip-studio/web test`（52 passed）；Contracts 专项 8 passed；Vite/TypeScript build 成功；SQLite Alembic 全生命周期与 `alembic check` 通过；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(export): generate PNG manga pages`。


### Task 2: 工程 ZIP 备份/恢复与完整性校验

**Files:**
- Create: `services/api/app/export/project_bundle.py; services/api/app/api/project_import.py; services/api/app/schemas/project_bundle.py`
- Create: `packages/contracts/src/project-manifest.ts`
- Modify: `services/api/app/main.py; packages/contracts/package.json`
- Test: `services/api/tests/test_project_bundle.py`
- Test: `packages/contracts/src/project-manifest.test.ts`

**Interfaces:**
- Consumes: DocumentRevision 与所有引用的 AssetVersion/Blob
- Produces: `export_project_bundle(episode_id: UUID, revision: int) -> bytes`; `import_project_bundle(payload: bytes) -> ImportResult`；manifest 保存 schema_version 与 blobs sha256

- [x] **Step 1: Write the failing test** — 覆盖 ZIP 往返、缺失/篡改 Blob、跨 IP 版本映射、路径穿越、符号链接和 ZIP bomb；manifest 合同检查 hash 路径及版本一致性。
- [x] **Step 2: Verify RED** — 首轮后端集成测试因 bundle 路由返回 404 而失败，manifest 合同因模块缺失而无法导入，均是预期缺失行为。
- [x] **Step 3: Implement minimally** — ZIP manifest + JSON 文档 + 全部引用原图；导入严格校验、临时解压和 SHA-256 验证后才开启持久化事务；重映射跨 IP 资产/模板/画风版本，创建新系列与新单集，不覆盖现有项目。
- [x] **Step 4: Verify GREEN** — 后端专项 `uv run --project services/api pytest -q services/api/tests/test_project_bundle.py`（12 passed）；完整后端 `uv run --project services/api pytest -q`（92 passed）；manifest 合同专项（3 passed）；完整前端/合同 Vitest（55 passed）；Vite/TypeScript build 与 `git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(export): add verifiable editable project zip`.


### Task 3: 原生对象 PPTX 导出

**Files:**
- Create: `apps/web/src/features/export/exportPptx.ts; apps/web/src/features/export/pptxMapper.ts`
- Test: `apps/web/src/features/export/pptxMapper.test.ts; apps/web/src/features/export/exportPptx.test.ts`

**Interfaces:**
- Consumes: CanvasDocumentV1 + 品牌外壳 + 独立 image/text/shape/chat 元素
- Produces: `mapCanvasElementToPptx(element: CanvasElement, context: PptxContext): PptxObject[]`; `exportEpisodePptx(doc: CanvasDocumentV1): Promise<Blob>`

- [x] **Step 1: Write the failing test** — `test_pptx_contains_text_and_multiple_picture_shapes`；用 jszip/PPTX XML 检查存在独立文本框和多图片/形状节点，不能仅整页一个 raster
- [x] **Step 2: Verify RED** — 首轮测试因 `pptxMapper` 与 `exportPptx` 模块缺失而按预期失败。
- [x] **Step 3: Implement minimally** — PptxGenJS 为每页建纵向 slide，独立生成文字、气泡背景/尾巴、聊天组件、角色图片；复杂裁切或字体不等价时 warnings[] 告警
- [x] **Step 4: Verify GREEN** — PPTX Mapper/导出专项 7 passed；完整前端 Vitest 63 passed；Vite/TypeScript production build 成功；LibreOffice 将生成的 PPTX 成功转换为 PDF；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(export): create element-editable pptx manga`。


### Task 4: EP01 / EP02 回归和 AC-01～AC-26 验收

**Files:**
- Create: `tests/e2e/ip-studio.spec.ts; tests/e2e/fixtures/ip-studio-seed.json`
- Create: `docs/qa/V1-acceptance-matrix.md; docs/qa/V1-manual-runbook.md`
- Test: `services/api/tests/test_acceptance_smoke.py`

**Interfaces:**
- Consumes: 所有已合并阶段 01–04；能创建真实 demo IP 与可再分发素材 fixture
- Produces: `tests/e2e/ip-studio.spec.ts` 端到端流程；验收矩阵每项链接自动化或人工证据

- [x] **Step 1: Write the failing test** — 新增 `ep01_dialogue_direction_brand_stability_and_pptx / generation_fallback_works`，覆盖 EP01 左“在吗？”右“不在。”、跨期模板一致、定域编辑、保存刷新与 PPTX 独立对象；另覆盖手动生图候选入审。
- [x] **Step 2: Verify RED** — E2E/验收回归作为新功能验收入口加入；开发期浏览器调试复现窄视口画布落到页栏下方的问题，并确认剧本输入回调会读到旧 React state，随后以修复和浏览器回归验证。
- [x] **Step 3: Implement minimally** — 接入 Series/Episode/Canvas 工作流、多选/原子组变换、文本溢出提示、手动 ChatGPT 生图候选审核及多格式导出；建立 AC-01～AC-26 验收矩阵，外部 runtime 缺失项明确标 `BLOCKED`。
- [x] **Step 4: Verify GREEN** — `bash scripts/verify-v1.sh` 全绿：后端 94 passed、前端 66 passed、Playwright 8 passed（包含保存中继续编辑回归）、Vite/TypeScript build 成功；保存 EP02 Playwright 截图。另 AC-18 真实 PostgreSQL + Blob 恢复通过；AC-25 是验收矩阵唯一 `BLOCKED` 项。远端 GitHub Actions、发布版本验证日志和生产配置检查仍未完成，见发布检查表。
- [x] **Step 5: Commit** — `git add tests/e2e docs/qa services/api/tests/test_acceptance_smoke.py && git commit -m "test(e2e): verify IP Studio V1 scenarios"`.


### Task 5: 本地部署、备份/恢复与交接审核

**Files:**
- Create: `docs/deployment/local-development.md; docs/deployment/backup-restore.md`
- Create: `scripts/verify-v1.sh; .github/workflows/ci.yml`
- Test: `docs/qa/V1-release-checklist.md`

**Interfaces:**
- Consumes: 所有功能与 AC 验收报告
- Produces: `scripts/verify-v1.sh` 统一执行可用的后端、前端和 E2E 测试，并返回准确 exit status；真实备份恢复说明

- [x] **Step 1: Write the failing test** — 脚本 failure-propagation 行为以临时 `uv` shim 注入 exit code `37` 验证；部署、备份/恢复与 release gate 的可复演条件写入对应 Runbook/Checklist。
- [x] **Step 2: Verify RED** — 开发前 `scripts/verify-v1.sh` 不存在；新脚本故障注入后保留首个后端命令的原始退出码，不再继续执行后续步骤。
- [x] **Step 3: Implement minimally** — 新增本地开发指南、PG + Blob 备份恢复步骤、完整验证脚本、Playwright 与 PostgreSQL migration CI；真实恢复和 API-owned Codex ImageGen 结果如实留在发布检查表。
- [x] **Step 4: Verify GREEN** — `bash scripts/verify-v1.sh` 全绿（94 backend / 66 Vitest / 8 Chromium E2E / build）；CI YAML 与 Compose 配置解析通过；PostgreSQL 17.11 真实 migration lifecycle 与 DB/Blob restore 通过。当前只有 AC-25 原生服务端探测仍阻断发布。
- [ ] **Release gate** — 验收矩阵不含 `BLOCKED` 项后方可视为最终发布完成；AC-25 当前仍 `BLOCKED`。
- [x] **Step 5: Commit** — `git add docs/deployment docs/qa/V1-release-checklist.md scripts/verify-v1.sh .github/workflows/ci.yml && git commit -m "docs(release): provide V1 verification and recovery runbooks"`.

