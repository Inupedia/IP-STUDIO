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

- [x] **Step 1: Write the failing test** — `test_layouts.py` 覆盖 4/6/8 格数量与不重叠、品牌引用和内容保留、缩减布局不丢内容、自定义布局几何校验；`LayoutPicker.test.tsx` 覆盖选择行为和品牌版本显示。
- [x] **Step 2: Run the test to verify RED** — 首次运行时 Python 缺少 `app.services.layouts`，Vitest 找不到 `LayoutPicker`，均按预期失败。
- [x] **Step 3: Implement the minimal behavior** — 前后端实现一致的两列/边距/间距几何、4/6/8 预设与 custom 数据 schema；应用布局保留品牌版本与原有图层，若移除非空画格则拒绝。
- [x] **Step 4: Run test to verify GREEN** — 专项后端 6 passed；完整后端 `uv run --project services/api pytest -v`（32 passed）；完整前端 Vitest（10 passed）；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(layout): add four six eight panel layouts`。


### Task 3: CanvasDocument v1 与消息方向协议

**Files:**
- Create: `packages/contracts/src/canvas.ts; packages/contracts/fixtures/canvas-v1.json`
- Create: `services/api/app/schemas/canvas.py`
- Test: `packages/contracts/src/canvas.test.ts; services/api/tests/test_canvas_contract.py`

**Interfaces:**
- Consumes: Brand/布局协议和 AssetVersion 引用
- Produces: `parseCanvasDocument(input: unknown): CanvasDocumentV1`; `resolveMessageSide(senderId: string, selfId: string): 'left'|'right'`；Python Pydantic 同名网络字段

- [x] **Step 1: Write the failing test** — 共享 fixture 与 TS/Python 测试覆盖必需品牌版本、snake_case、非法 asset version UUID 和 EP01 左右消息派生。
- [x] **Step 2: Run the test to verify RED** — Vitest 因 `./canvas` 缺失而导入失败；pytest 因 `app.schemas.canvas` 不存在而收集失败。
- [x] **Step 3: Implement the minimal behavior** — 实现 1.0 文档、页面、画格、8 种元素及严格字段 schema；图片裁切 0–1 约束、画格边界、每页品牌版本一致性、消息方向函数和共享 JSON fixture。
- [x] **Step 4: Run test to verify GREEN** — Canvas 专项 TS 3 passed、Python 3 passed；完整后端 35 passed、完整前端 13 passed；contracts TypeScript strict check 与 Vite build 成功。
- [x] **Step 5: Commit** — `feat(editor): specify editable canvas document v1`。


### Task 4: 画布品牌层及独立内容图层

**Files:**
- Create: `apps/web/src/features/editor/ComicEditor.tsx; apps/web/src/features/editor/BrandLayer.tsx`
- Create: `apps/web/src/features/editor/PanelLayer.tsx; apps/web/src/features/editor/CanvasToolbar.tsx`
- Test: `apps/web/src/features/editor/ComicEditor.test.tsx`

**Interfaces:**
- Consumes: CanvasDocumentV1 + BrandTemplateV1
- Produces: `ComicEditor({document,brand,onChange})`，品牌背景/前景不可选择，标题内容与 image/text/shape 可交互

- [x] **Step 1: Write the failing test** — `ComicEditor.test.tsx` 覆盖 Logo/页脚不能选择拖动、标题通过固定属性槽编辑，以及不同标题下品牌元素坐标完全一致。
- [x] **Step 2: Run the test to verify RED** — 测试在 `ComicEditor` 尚未实现时因模块不存在而失败；实现后再修正测试清理与节点文本 mock。
- [x] **Step 3: Implement the minimal behavior** — 使用 React Konva 分层绘制不可交互品牌背景/前景与画格裁切内容；支持图层选择、拖动/缩放/旋转、图片裁切显示、聊天方向、缩放/网格/安全区、页面切换、属性栏和布局选择。
- [x] **Step 4: Run test to verify GREEN** — 编辑器专项 2 passed；完整前端 15 passed；`pnpm --filter @ip-studio/web build` 和 contracts strict TypeScript check 成功；`git diff --check` 通过。
- [x] **Step 5: Commit** — `feat(editor): render fixed shell and editable manga canvas`。


### Task 5: 图层编辑、撤销保存、并发冲突

**Files:**
- Create: `apps/web/src/features/editor/commands.ts; apps/web/src/features/editor/DocumentStore.ts`
- Create: `apps/web/src/features/editor/elements/ChatMessage.tsx; apps/web/src/features/editor/elements/TextElement.tsx; services/api/app/services/documents.py; services/api/app/api/documents.py`
- Test: `apps/web/src/features/editor/commands.test.ts; services/api/tests/test_document_conflicts.py`

**Interfaces:**
- Consumes: CanvasDocumentV1 和品牌锁定层
- Produces: `applyCanvasCommand(doc: CanvasDocumentV1, cmd: CanvasCommand): CanvasDocumentV1`; `save_document(episode_id: UUID, base_revision: int, payload: dict) -> DocumentRevision`

- [x] **Step 1: Write the failing test** — `commands.test.ts` 覆盖独立修改文字/图片、undo/redo 与锁定拒改；`DocumentStore.test.tsx` 覆盖 debounce、保存冲突停重试与保存期间编辑排队；`test_document_conflicts.py` 覆盖 CAS 409、外壳版本锁、历史恢复和跨 IP 资产拒绝。
- [x] **Step 2: Run the test to verify RED** — 前端首先因缺少 `commands` 模块失败；后端文档请求在路由实现前返回 404。额外并发回归在修复前观察到保存中又启动第二个请求。
- [x] **Step 3: Implement the minimal behavior** — 实现白名单画布命令、50 步历史、1.5 秒 debounce、并发保存串行排队、双击原生 DOM 文本编辑、图片替换/裁切和独立聊天/文字组件；服务端校验同 workspace/IP 的已批准引用，以 `base_revision` 原子 CAS 保存快照，并提供 revision 查看与无损恢复。
- [x] **Step 4: Run test to verify GREEN** — `uv run --project services/api pytest -v`（39 passed）；`pnpm --filter @ip-studio/web test`（21 passed）；`pnpm --filter @ip-studio/web build` 成功；SQLite 上 Alembic upgrade、`alembic check`、downgrade base、upgrade head 全通过；`git diff --check` 通过。PostgreSQL runtime smoke test 因本机 Docker daemon 未运行、无本地 PostgreSQL 而未执行。
- [x] **Step 5: Commit** — `feat(editor): add PPT-style layers with safe history`。

