# 02 — Brand Templates and Editable Canvas Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现锁定 IP 品牌外壳、可选画格布局与 PPT 式漫画图层编辑器。

**Architecture:** BrandTemplateVersion 静态锁定外壳和 Episode 动态内容分离；Zod 协议作为画布唯一源，Konva 负责展示与交互，FastAPI 对编辑命令做服务器二次校验。

**Tech Stack:** React Konva, Zustand, Zod, FastAPI, PostgreSQL, Vitest, pytest

**Spec:** `docs/product/PRD-v1.md`; `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`

## Global Constraints

- 单工作室管理员、多 IP；所有读写校验 workspace/ip 归属，网络 JSON 使用 snake_case。
- 批准后的角色、风格、素材、品牌版本不可覆写；工程有独立 `schema_version = "1.0"`。
- 品牌外壳锁定，标题文字和剧情动态；聊天气泡及中文为独立可编辑对象。
- 不能把 ChatGPT Plus 当作开发者 API；Codex ImageGen 只有真实自检通过后才启用。
- 先写失败测试再最小实现、测试通过后提交；不能将计划任务假报为已实现。

## Review Focus

- 编辑器试图移动锁定 Logo → 拒绝（Task 1/4）
- 发布品牌 v1.1 后 EP01 仍引用 v1.0 → 不变（Task 1/2）
- 四/六/八格布局每格互不重叠 → 验证（Task 2）
- 聊天消息 sender=卡仔 在右 → 稳定（Task 3/5）
- 两个标签页写相同 revision → 后者收到 409（Task 5）

---

### Task 1: 品牌模板的数据约束与批准冻结

**Files:**
- Create: `services/api/app/models/templates.py; services/api/app/services/templates.py`
- Create: `services/api/app/api/templates.py; services/api/alembic/versions/0004_templates.py; packages/contracts/src/brand.ts`
- Test: `services/api/tests/test_templates.py`

**Interfaces:**
- Consumes: 01 阶段 IP 和 AssetVersion
- Produces: `create_brand_candidate(ip_id: UUID, source_version_id: UUID|None) -> BrandTemplateVersion`; `approve_brand_version(id: UUID) -> BrandTemplateVersion`；动态 slots: title/episode_number/content

- [x] **Step 1: Write the failing test** — `test_templates.py` 覆盖批准冻结与派生、跨 IP 拒绝、普通文档外壳修改拒绝；补充 Zod 模板契约测试。
- [x] **Step 2: Run the test to verify RED** — 后端专项测试因 `app.services.templates` 尚不存在而在收集时失败；后续完成实现后转绿。
- [x] **Step 3: Implement the minimal behavior** — 建立 IP-scoped BrandTemplate/BrandTemplateVersion、候选/审批/派生 API 和迁移；品牌静态元素与标题/期号动态槽位分开，版本引用素材需同 IP 已批准；共享服务校验拒绝普通文档变更外壳。
- [x] **Step 4: Run test to verify GREEN** — `uv run --project services/api pytest -v`（26 passed）；`pnpm --filter @ip-studio/web test`（含 brand schema 测试，4 passed）；`pnpm --filter @ip-studio/web build` 成功；SQLite Alembic upgrade/check/downgrade/upgrade 通过；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(template): add frozen IP brand templates`。


### Task 2: 4/6/8 格布局与页面继承

**Files:**
- Create: `packages/contracts/src/layout.ts; services/api/app/services/layouts.py`
- Create: `apps/web/src/features/templates/LayoutPicker.tsx`
- Test: `apps/web/src/features/templates/LayoutPicker.test.tsx; services/api/tests/test_layouts.py`

**Interfaces:**
- Consumes: BrandTemplateVersion 和 Episode ID
- Produces: `get_layout(code: 'four'|'six'|'eight') -> LayoutTemplate`; `apply_layout(page, layout) -> PageDocument`；Page 记录 brand_template_version_id

- [ ] **Step 1: Write the failing test** — `test_four_six_eight_counts / test_layout_preserves_brand_version`: 每种布局画格数正确且不重叠；替换布局不修改品牌
- [ ] **Step 2: Run the test to verify RED** — `cd services/api && uv run pytest tests/test_layouts.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/templates/LayoutPicker.test.tsx`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 实现可选择且确定性的 panel geometry；提供自定义布局数据格式及页面冻结关联
- [ ] **Step 4: Run test to verify GREEN** — `cd services/api && uv run pytest tests/test_layouts.py -v && cd ../../ && pnpm --dir apps/web exec vitest run src/features/templates/LayoutPicker.test.tsx`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add packages/contracts/src/layout.ts services/api/app/services/layouts.py apps/web/src/features/templates services/api/tests/test_layouts.py && git commit -m "feat(layout): add four six eight panel layouts"`.


### Task 3: CanvasDocument v1 与消息方向协议

**Files:**
- Create: `packages/contracts/src/canvas.ts; packages/contracts/fixtures/canvas-v1.json`
- Create: `services/api/app/schemas/canvas.py`
- Test: `packages/contracts/src/canvas.test.ts; services/api/tests/test_canvas_contract.py`

**Interfaces:**
- Consumes: Brand/布局协议和 AssetVersion 引用
- Produces: `parseCanvasDocument(input: unknown): CanvasDocumentV1`; `resolveMessageSide(senderId: string, selfId: string): 'left'|'right'`；Python Pydantic 同名网络字段

- [ ] **Step 1: Write the failing test** — `canvas.test.ts: requires_brand_template_version / sender_direction_is_deterministic`: schema_version=1.0；卡仔回复右侧，朋友左侧；错误资产引用被拒
- [ ] **Step 2: Run the test to verify RED** — `pnpm --dir apps/web exec vitest run ../../packages/contracts/src/canvas.test.ts && cd ../../ && cd services/api && uv run pytest tests/test_canvas_contract.py -v`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 实现类型、fixtures、交叉语言校验和迁移预留；Zod/后端字段一致
- [ ] **Step 4: Run test to verify GREEN** — `pnpm --dir apps/web exec vitest run ../../packages/contracts/src/canvas.test.ts && cd ../../ && cd services/api && uv run pytest tests/test_canvas_contract.py -v`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add packages/contracts services/api/app/schemas/canvas.py services/api/tests/test_canvas_contract.py && git commit -m "feat(editor): specify editable canvas document v1"`.


### Task 4: 画布品牌层及独立内容图层

**Files:**
- Create: `apps/web/src/features/editor/ComicEditor.tsx; apps/web/src/features/editor/BrandLayer.tsx`
- Create: `apps/web/src/features/editor/PanelLayer.tsx; apps/web/src/features/editor/CanvasToolbar.tsx`
- Test: `apps/web/src/features/editor/ComicEditor.test.tsx`

**Interfaces:**
- Consumes: CanvasDocumentV1 + BrandTemplateV1
- Produces: `ComicEditor({document,brand,onChange})`，品牌背景/前景不可选择，标题内容与 image/text/shape 可交互

- [ ] **Step 1: Write the failing test** — `ComicEditor.test.tsx: logo_not_selectable_and_title_editable`: Logo/页脚不能拖动；标题值可编辑但位置不可动；相同品牌生成相同外框
- [ ] **Step 2: Run the test to verify RED** — `pnpm --dir apps/web exec vitest run src/features/editor/ComicEditor.test.tsx`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — React Konva 分层渲染，画格 clip、画布缩放与 Transformer，设置独立可编辑对象树
- [ ] **Step 4: Run test to verify GREEN** — `pnpm --dir apps/web exec vitest run src/features/editor/ComicEditor.test.tsx`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add apps/web/src/features/editor && git commit -m "feat(editor): render fixed shell and editable manga canvas"`.


### Task 5: 图层编辑、撤销保存、并发冲突

**Files:**
- Create: `apps/web/src/features/editor/commands.ts; apps/web/src/features/editor/DocumentStore.ts`
- Create: `apps/web/src/features/editor/elements/ChatMessage.tsx; apps/web/src/features/editor/elements/TextElement.tsx; services/api/app/services/documents.py; services/api/app/api/documents.py`
- Test: `apps/web/src/features/editor/commands.test.ts; services/api/tests/test_document_conflicts.py`

**Interfaces:**
- Consumes: CanvasDocumentV1 和品牌锁定层
- Produces: `applyCanvasCommand(doc: CanvasDocumentV1, cmd: CanvasCommand): CanvasDocumentV1`; `save_document(episode_id: UUID, base_revision: int, payload: dict) -> DocumentRevision`

- [ ] **Step 1: Write the failing test** — `commands.test.ts: undo_redo_text_and_image / locked_element_rejected; test_document_conflict_returns_409`: 变更一个图层不影响其他格；undo 正确；冲突绝不覆盖；聊天方向正确
- [ ] **Step 2: Run the test to verify RED** — `pnpm --dir apps/web exec vitest run && cd services/api && uv run pytest tests/test_document_conflicts.py -v`; expected **FAIL** because the behavior has not been implemented.
- [ ] **Step 3: Implement the minimal behavior** — 实现图片替换/裁切、文本双击 DOM 编辑、气泡/消息/锁层、50 步命令历史、1–3 秒 autosave 与 CAS 服务端校验
- [ ] **Step 4: Run test to verify GREEN** — `pnpm --dir apps/web exec vitest run && cd services/api && uv run pytest tests/test_document_conflicts.py -v`; expected **PASS**. Run neighboring regression tests.
- [ ] **Step 5: Commit** — `git add apps/web/src/features/editor services/api/app/services/documents.py services/api/app/api/documents.py services/api/tests/test_document_conflicts.py && git commit -m "feat(editor): add PPT-style layers with safe history"`.

