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
- Produces: `create_script_revision(episode_id: UUID, script: dict) -> ScriptRevision`; `materialize_panels(episode_id: UUID, revision_id: UUID) -> list[Panel]`

- [ ] **Step 1: Write the failing test** — `test_script_revision_immutable / test_resync_requires_confirmation`；修改剧本创建新修订；有旧内容图层时需要确认才同步新的对白
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_scripts.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/production/ScriptEditor.test.tsx`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 存储场景/角色/对话/镜头定义与 revision；提供人工文本编辑、分镜卡和变更预览
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_scripts.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/production/ScriptEditor.test.tsx`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app apps/web/src/features/production services/api/tests/test_scripts.py && git commit -m "feat(story): add versioned scripts and storyboard"`.


### Task 2: 参考资产打包与无字提示词

**Files:**
- Create: `services/api/app/services/prompt_builder.py; services/api/app/services/reference_bundle.py`
- Create: `services/api/app/api/generation_tasks.py; apps/web/src/features/production/GenerationTaskCard.tsx`
- Test: `services/api/tests/test_prompt_builder.py; services/api/tests/test_generation_tasks.py`

**Interfaces:**
- Consumes: 已批准 CharacterVersion / StyleVersion / AssetVersion，Panel 描述
- Produces: `build_prompt(panel_id: UUID, refs: list[UUID]) -> PromptSnapshot`; `create_reference_bundle(task_id: UUID) -> bytes`; `create_generation_task(episode_id: UUID, mode: str) -> GenerationTask`

- [ ] **Step 1: Write the failing test** — `test_prompt_contains_locked_version_ids_and_no_text / test_references_belong_to_ip`；提示词要求单格、无字、禁止页码/水印，且角色与风格参考真实、IP 范围合法
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_prompt_builder.py tests/test_generation_tasks.py -v`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 生成结构化任务卡，完整引用快照，构建 ZIP 参考包与复制提示词 UI；人工任务状态 prepared/waiting_manual_generation/asset_imported
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_prompt_builder.py tests/test_generation_tasks.py -v`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/services/prompt_builder.py services/api/app/services/reference_bundle.py services/api/app/api/generation_tasks.py apps/web/src/features/production/GenerationTaskCard.tsx services/api/tests && git commit -m "feat(production): add generation prompts and reference bundles"`.


### Task 3: 浏览器拖拽、粘贴与候选入库

**Files:**
- Create: `apps/web/src/features/production/ImportAssetDropzone.tsx; apps/web/src/features/production/useClipboardImage.ts`
- Create: `services/api/app/services/candidate_assets.py; services/api/app/api/generation_candidates.py`
- Test: `apps/web/src/features/production/ImportAssetDropzone.test.tsx; services/api/tests/test_candidates.py`

**Interfaces:**
- Consumes: Phase 01 安全上传服务和 GenerationTask
- Produces: `import_candidate(task_id: UUID, asset_version_id: UUID) -> GenerationCandidate`; `pasteClipboardImage(targetPanelId: string, file: File): Promise<AssetVersion>`

- [ ] **Step 1: Write the failing test** — `test_import_candidate_matches_task_ip / ClipboardPaste routes to selected panel`；文件落 candidate 状态；无 active panel 不能默默关联；跨 IP 资产拒绝
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_candidates.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/production/ImportAssetDropzone.test.tsx`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 实现拖拽/选择/粘贴图片上传并绑定任务，失败提示、格式检查及浏览器剪贴板权限反馈
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_candidates.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/production/ImportAssetDropzone.test.tsx`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/services/candidate_assets.py services/api/app/api/generation_candidates.py services/api/tests/test_candidates.py apps/web/src/features/production && git commit -m "feat(production): import ChatGPT output as candidate assets"`.


### Task 4: 候选审核、替换单格与可复用素材

**Files:**
- Create: `services/api/app/services/candidate_review.py; apps/web/src/features/production/CandidateReview.tsx`
- Create: `apps/web/src/features/editor/ReplacePanelImage.tsx`
- Test: `services/api/tests/test_candidate_review.py; apps/web/src/features/editor/ReplacePanelImage.test.tsx`

**Interfaces:**
- Consumes: GenerationCandidate 和 Phase 02 画布 command
- Produces: `approve_candidate(candidate_id: UUID) -> AssetVersion`; `replace_panel_image(panel_id: string, assetVersionId: string) -> CanvasCommand`

- [ ] **Step 1: Write the failing test** — `test_rejected_candidate_cannot_bind / replace_image_does_not_modify_chat_or_brand`；被拒绝素材不能用于批准画格；替换只触及选中 image 层，保持模板、标题、台词不变
- [ ] **Step 2: Verify RED** — Run `cd services/api && uv run pytest tests/test_candidate_review.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/editor/ReplacePanelImage.test.tsx`；expected **FAIL** for missing behavior, not missing dependencies.
- [ ] **Step 3: Implement minimally** — 候选池、接受/拒绝记录、复用检索与替换当前画格；旧扁平图片只导入为参考 asset
- [ ] **Step 4: Verify GREEN** — Run `cd services/api && uv run pytest tests/test_candidate_review.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/editor/ReplacePanelImage.test.tsx`；expected **PASS**. Also run relevant regression suite.
- [ ] **Step 5: Commit** — `git add services/api/app/services/candidate_review.py services/api/tests/test_candidate_review.py apps/web/src/features/production apps/web/src/features/editor && git commit -m "feat(production): add candidate review and panel replacement"`.

