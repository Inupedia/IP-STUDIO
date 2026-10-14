# 03 — Storyboard and Content Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在可编辑品牌画布上实现剧本、分镜、可复制生成提示词、参考素材包和 ChatGPT 人工生图回流。

**Architecture:** Series/Episode 保存独立剧本修订与 Panel 规划；GenerationTask 保存参考图/提示词快照，网页人工回退路径不依赖 Codex。候选图片审核后才成为画格素材。

**Tech Stack:** FastAPI, Pydantic, PostgreSQL, React, TypeScript, Zod, Pillow, pytest, Vitest, Playwright

**Spec:** `docs/product/PRD-v1.md`; `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`

## Global Constraints

- 单管理员、多 IP；从请求到文件路径均校验 workspace / ip 归属。
- 角色、画风、品牌、资产批准版不可覆盖；画布工程 `schema_version = "1.0"`，默认 1080×1440 px。
- IP 品牌外壳固定，仅标题**文本**和剧情/分镜动态；ImageGen 只生成无字位图；中文消息独立渲染。
- Codex 生图仅在实际能力探测通过时启用；在线 ChatGPT 人工生图/导入必须一直可用；不使用私人端点/Cookie/隐式付费 API。
- 每个 Task 必须 RED → GREEN → Commit，确保提交真实测试与验收证据。

## Review Focus

- 剧本文字变化不自动覆盖已定稿台词图层（Task 1）
- ChatGPT 模板中错误关联别的 IP 的参考图 → 拒绝（Task 2）
- 手动粘贴图片没有对应任务 → 要求明确分配（Task 3）
- 候选被拒绝仍然保留审核记录，不能进入正式画格（Task 4）
- 图片含乱码旧对白的扁平页 → 只能当参考，不能谎称自动拆图层（Task 4）

---

### Task 1: 剧本 Revision、场景、分镜持久化

**Files:**
- Create: `services/api/app/models/scripts.py; services/api/app/services/scripts.py; services/api/app/api/scripts.py`
- Create: `apps/web/src/features/production/ScriptEditor.tsx; apps/web/src/features/production/Storyboard.tsx`
- Test: `services/api/tests/test_scripts.py; apps/web/src/features/production/ScriptEditor.test.tsx`

**Interfaces:**
- Consumes: Phase 01 Series/Episode、Phase 02 CanvasDocumentV1
- Produces: `create_script_revision(episode_id: UUID, base_revision: int, script: ScriptV1) -> ScriptRevision`; `materialize_panels(episode_id: UUID, revision_no: int, base_document_revision: int, confirm_dialogue_sync: bool) -> ScriptMaterializationResult`

- [x] **Step 1: Write the failing test** — `test_scripts.py` 覆盖追加修订与旧版读取、对白同步确认、确认后仅更新对应消息/气泡对象，以及角色版本未批准/跨 IP 拒绝；`ScriptEditor.test.tsx` 覆盖结构化对白保存为新修订与画布同步差异预览。
- [x] **Step 2: Verify RED** — 后端新路由实现前返回 404；前端因缺少 `ScriptEditor` 模块无法解析测试导入，均按预期 RED。
- [x] **Step 3: Implement minimally** — 新增不可覆写的 ScriptRevision、1.0 TS/Python 结构契约、IP/批准引用校验和 revision API；分镜卡由固定脚本修订生成；剧本与画布内容分开存储，确认同步时仅改匹配的 chat_message/speech_bubble `props.text`，并沿用画布 CAS 保存。提供 Markdown/结构场景/对白/镜头编辑及差异确认 UI。
- [x] **Step 4: Verify GREEN** — `uv run --project services/api pytest -v`（42 passed）；`pnpm --filter @ip-studio/web test`（25 passed）；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。SQLite Alembic upgrade、`alembic check`（无差异）、downgrade base、upgrade head 全通过。PostgreSQL runtime smoke test 仍受 Docker/PostgreSQL 本地环境限制。
- [x] **Step 5: Commit** — `feat(story): add versioned scripts and storyboard`。


### Task 2: 参考资产打包与无字提示词

**Files:**
- Create: `services/api/app/services/prompt_builder.py; services/api/app/services/reference_bundle.py`
- Create: `services/api/app/api/generation_tasks.py; apps/web/src/features/production/GenerationTaskCard.tsx`
- Test: `services/api/tests/test_prompt_builder.py; services/api/tests/test_generation_tasks.py`

**Interfaces:**
- Consumes: 已批准 CharacterVersion / StyleVersion / AssetVersion，Panel 描述
- Produces: `build_prompt(panel_id: UUID, refs: list[UUID]) -> PromptSnapshot`; `create_reference_bundle(task_id: UUID) -> bytes`; `create_generation_task(episode_id: UUID, mode: str) -> GenerationTask`

- [x] **Step 1: Write the failing test** — `test_prompt_contains_locked_version_ids_and_no_text / test_references_belong_to_ip`；覆盖无字约束、对白不泄漏、准确角色/画风版本、ZIP 图片清单、跨 IP/候选版本拒绝和手动任务状态。
- [x] **Step 2: Verify RED** — 后端测试因 `app.services.prompt_builder` 不存在而无法收集，前端测试因 `GenerationTaskCard` 不存在而无法解析导入；均由缺少实现触发，无缺失依赖。
- [x] **Step 3: Implement minimally** — 新增 GenerationTask 快照与迁移、批准角色/画风/图片版本和同 IP 校验、无字提示构建、校验 SHA-256 的参考 ZIP、人工任务读取/状态 API、复制提示词和下载参考包任务卡及 Zod 合同。当前仅开放 `chatgpt_web` 人工模式，不探测或调用私有 API。
- [x] **Step 4: Verify GREEN** — 专项后端 3 passed、完整后端 45 passed；前端 29 passed、GenerationTask 合同 2 passed；Vite/TypeScript build 成功；SQLite `0007_generation_tasks` upgrade、`alembic check`、downgrade base、upgrade head 均通过；`git diff --check` 通过。PostgreSQL runtime smoke test 仍受 Docker/PostgreSQL 本地环境限制。
- [x] **Step 5: Commit** — `feat(production): add generation prompts and reference bundles`。


### Task 3: 浏览器拖拽、粘贴与候选入库

**Files:**
- Create: `apps/web/src/features/production/ImportAssetDropzone.tsx; apps/web/src/features/production/useClipboardImage.ts`
- Create: `services/api/app/services/candidate_assets.py; services/api/app/api/generation_candidates.py`
- Test: `apps/web/src/features/production/ImportAssetDropzone.test.tsx; services/api/tests/test_candidates.py`

**Interfaces:**
- Consumes: Phase 01 安全上传服务和 GenerationTask
- Produces: `import_candidate(task_id: UUID, asset_version_id: UUID) -> GenerationCandidate`; `pasteClipboardImage(targetPanelId: string, file: File): Promise<AssetVersion>`

- [x] **Step 1: Write the failing test** — `test_import_candidate_matches_task_ip / ClipboardPaste routes to selected panel`；覆盖 candidate 状态、任务画格绑定、重复/跨 IP/未启动任务拒绝、无选中画格不上传及浏览器拖放/粘贴。
- [x] **Step 2: Verify RED** — API 绑定路由实现前返回 404；前端因 `ImportAssetDropzone` 模块不存在而无法解析导入；均由缺少功能实现触发，无缺失依赖。
- [x] **Step 3: Implement minimally** — 增加任务候选模型/迁移与 IP-scoped 绑定 API；安全资产上传后绑定候选并创建 `AssetLink` 防止候选素材被误删；实现拖放、选择文件、`Ctrl+V` 和主动读取剪贴板，缺少选中画格、任务不匹配、格式错误或剪贴板权限拒绝时显示反馈，不自动关联默认画格。
- [x] **Step 4: Verify GREEN** — 专项后端 2 passed、完整后端 47 passed；前端 34 passed、GenerationCandidate 合同 3 passed；Vite/TypeScript build 成功；SQLite `0008_generation_candidates` upgrade、`alembic check`、downgrade base、upgrade head 均通过；`git diff --check` 通过。PostgreSQL runtime smoke test 仍受 Docker/PostgreSQL 本地环境限制。
- [x] **Step 5: Commit** — `feat(production): import ChatGPT output as candidate assets`。


### Task 4: 候选审核、替换单格与可复用素材

**Files:**
- Create: `services/api/app/services/candidate_review.py; apps/web/src/features/production/CandidateReview.tsx`
- Create: `apps/web/src/features/editor/ReplacePanelImage.tsx`
- Test: `services/api/tests/test_candidate_review.py; apps/web/src/features/editor/ReplacePanelImage.test.tsx`

**Interfaces:**
- Consumes: GenerationCandidate 和 Phase 02 画布 command
- Produces: `approve_candidate(candidate_id: UUID) -> AssetVersion`; `replace_panel_image(panel_id: string, assetVersionId: string) -> CanvasCommand`

- [x] **Step 1: Write the failing test** — `test_candidate_review.py` 覆盖批准/拒绝、拒绝后禁止重绑、重复拒绝冲突及通用审批绕过；`ReplacePanelImage.test.tsx` 覆盖仅替换目标图片并保持品牌、标题与聊天文字不变。
- [x] **Step 2: Verify RED** — 新路由/组件缺失时专项测试按预期失败；增加重复拒绝断言后观察到异常类型未映射导致 500，修正后再次通过。
- [x] **Step 3: Implement minimally** — 新增审核记录与管理员/时间约束、同 IP 候选池 API、批准/拒绝状态机和素材复用；阻止通用素材审批绕过候选审核；画布仅通过 `replace_image` 白名单命令改目标图层。拒绝记录保留，扁平页继续明确为不可拆分的参考位图。
- [x] **Step 4: Verify GREEN** — 专项后端 2 passed；完整后端 `uv run --project services/api pytest -q`（49 passed）；完整前端 `pnpm --filter @ip-studio/web test`（37 passed）；GenerationCandidate 合同 3 passed；`pnpm --filter @ip-studio/web build` 成功；SQLite `0009_candidate_reviews` upgrade、`alembic check`、downgrade base、upgrade head 全通过；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(production): add candidate review and panel replacement`。

