# IP Studio V1 实施进度

> 以 `docs/superpowers/plans/README.md` 中的正式顺序执行。日期使用 Asia/Shanghai。

## 阶段 01：工程基础与资产版本

### Task 1：工程底座与健康检查 — 已完成

- 提交：`chore: bootstrap V1 web API and test harness`
- RED 证据：`uv run --project services/api pytest services/api/tests/test_health.py -v` 返回预期 404；`pnpm --dir apps/web exec vitest run src/App.test.tsx` 因缺少可访问的 IP Studio 标题失败。
- GREEN 与构建：`pnpm --filter @ip-studio/web test`（1 passed）；`pnpm --filter @ip-studio/web build`；`uv run --project services/api pytest -v`（1 passed）。
- 工程验证：`pnpm install --frozen-lockfile --registry=https://registry.npmjs.org`；`uv sync --project services/api --locked --group dev`；`docker compose config -q`；`git diff --check`。
- 结果：React/Vite 工作区、FastAPI 健康端点、PostgreSQL Compose、环境变量示例和基础 CI 已建立。
- 边界：Compose 文件已校验，但本任务没有启动数据库容器；业务模型与 CRUD 属于后续任务。

### 后续任务

- [x] Task 2：Workspace / IP / Series / Episode 数据与 API
- [x] Task 3：安全上传 / Blob 去重 / AssetVersion
- [x] Task 4：Character Bible 与 Style Bible 批准版本
- [x] Task 5：多 IP 资产管理页面

#### Task 5 交付记录

- 提交：`feat(ui): implement IP asset and bible workspace`
- RED 证据：新增 AssetLibrary 测试后，在组件尚未实现时导入失败；GREEN 测试覆盖 IP 切换隔离、候选状态及审批请求中的 IP/Asset/Version。
- GREEN 与回归：`pnpm --filter @ip-studio/web test`（2 passed）；`pnpm --filter @ip-studio/web build` 成功；`uv run --project services/api pytest -v`（23 passed）；`git diff --check` 通过。
- 结果：管理员可登录并维护多个 IP，在当前 IP 内上传、筛选、预览、批准素材；角色与画风完整字段按候选→批准→派生管理，参考只显示同 IP 的已批准素材，版本快照可查看；默认画风只能选同 IP 已批准版本。
- 风险/限制：本任务覆盖登录、IP、素材和 Bible 工作区；其余模板、画布、分镜、生图与导出按后续计划完成。PostgreSQL 运行时限制见 Task 2–4。

#### Task 4 交付记录

- 提交：`feat(ip): introduce immutable character and style bibles`
- RED 证据：`uv run --project services/api pytest services/api/tests/test_bibles.py -v` 在 API 尚未实现时 4 项均因 Character/Style 路由返回 404 而失败。
- GREEN 与回归：专项 4 passed；完整后端 `uv run --project services/api pytest -v`（23 passed）；前端 `pnpm --filter @ip-studio/web test`（1 passed）及 `pnpm --filter @ip-studio/web build` 成功。
- 迁移验证：SQLite 上 upgrade head、`alembic check`（无新变更）、downgrade base、再次 upgrade，全部通过。
- 结果：角色与画风 Bible 使用结构化 JSON；版本仅能追加，已批准版本不能再次审批或被覆盖；新候选可基于已批准版本派生；审批记录管理员与时间；引用素材要求已批准且属于同一 IP；IP 默认画风仅接受本 IP 的已批准 StyleVersion。另补齐素材版本审批 API，供引用流程使用。
- 环境限制：本机 PostgreSQL 运行时仍受 Docker daemon 未运行及无本地 PostgreSQL 二进制影响；本任务以 SQLite API 测试和 Alembic 生命周期检查验证。

#### Task 3 交付记录

- 提交：`feat(assets): add immutable safe image asset registry`
- RED 证据：初次运行 `uv run --project services/api pytest services/api/tests/test_assets.py -v` 在收集阶段因 `app.models.assets` 尚不存在而失败。
- 素材验证：该文件 13 passed；完整后端 `uv run --project services/api pytest -v`（19 passed）；前端 `pnpm --filter @ip-studio/web test`（1 passed）及 `pnpm --filter @ip-studio/web build` 成功。
- 迁移验证：SQLite 上升级到 head、`alembic check`（无新变更）、回滚到 base、再升级，全部通过。
- 结果：只接受并完整解码 PNG/JPEG/WebP；限制默认 25 MiB/40 MP；按 SHA-256 原子存 Blob 并去重；资产、版本和下载按所属 IP 检查；新版本保留旧版本；删除需显式确认且引用中的版本返回 409，Blob 最后一个版本删除后才清理。
- 环境限制：Docker daemon 仍未运行，且无本地 PostgreSQL，因此本任务未执行 PostgreSQL 运行时冒烟；数据库路径目前由 SQLite 测试和 Alembic 生命周期验证覆盖。

#### Task 2 交付记录

- 提交：`feat(domain): add scoped IP and story models`
- RED 证据：新增三个唯一性/隔离测试后，在模型与路由实现前运行 `pytest tests/test_ips.py -v`，重复 IP、重复分集和跨 workspace 访问均因路由未实现而失败（405）。
- GREEN 与回归：`uv run --project services/api pytest -v`（6 passed）；`uv sync --project services/api --locked --group dev`。
- 数据迁移：SQLite 上执行 Alembic upgrade、`alembic check`（无新变更）、downgrade base、再次 upgrade，全部通过。
- 结果：建立单管理员 workspace、IP/Series/Episode 模型与迁移、workspace-scoped CRUD、JWT 登录及密码哈希；不同 workspace 的资源通过服务查询隔离，复合外键约束归属。
- 环境限制：本机 Docker daemon 未运行，且没有本地 PostgreSQL 二进制，因此本任务无法做 PostgreSQL 容器运行时冒烟；使用 SQLite 跑 API 测试和迁移生命周期验证。Task 1 的 Compose 配置检查已通过。
- 后续修复：阶段 02 复核发现后端布局 helper 会让预设 `panel-01` 覆盖已有 panel ID；新增回归断言确认 RED 后，在提交 `de883f6` 修正 ID 保留，前后端布局身份保持一致。

## 阶段 02：品牌模板与画布

- [x] Task 1：品牌模板的数据约束与批准冻结
- [x] Task 2：4/6/8 格布局与页面继承
- [x] Task 3：CanvasDocument v1 与消息方向协议
- [x] Task 4：画布品牌层及独立内容图层
- [x] Task 5：图层编辑、撤销保存、并发冲突

#### Task 1 交付记录

- 提交：`feat(template): add frozen IP brand templates`
- RED 证据：新增 API/service 测试后，首次运行因 `app.services.templates` 尚不存在而在收集时失败。
- GREEN 与回归：`uv run --project services/api pytest -v`（26 passed）；`pnpm --filter @ip-studio/web test`（含品牌协议 4 passed）；`pnpm --filter @ip-studio/web build` 成功；SQLite Alembic upgrade/check/downgrade/upgrade 通过。
- 结果：品牌模板按 IP 隔离，静态外壳和标题/期号槽位分别存储；批准版本不可覆盖，只能派生；锁定素材必须属于同 IP 且已批准；共享校验拒绝普通文档请求改动外壳。
- 限制：PostgreSQL 运行时仍受 Docker daemon 未启动及缺少本机 PostgreSQL 影响；改用 SQLite 测试和迁移生命周期验证。

#### Task 2 交付记录

- 提交：`feat(layout): add four six eight panel layouts`
- RED 证据：后端测试因 `app.services.layouts` 不存在而收集失败；前端测试因 `LayoutPicker` 尚不存在而导入失败。
- GREEN 与回归：布局专项后端 6 passed；完整后端 32 passed；完整前端 10 passed；Vite build 成功。
- 结果：前后端共享固定两列、48 px 外边距和 24 px 间距；4/6/8 布局可重复计算，custom 几何会校验边界和重叠；应用布局保留 `brand_template_version_id` 与已有图层，缩减后会移除含内容画格时明确拒绝。
- 风险/限制：布局选择器已具备可复用 UI，尚待 Task 4/5 接入完整 Episode 编辑器。

#### Task 3 交付记录

- 提交：`feat(editor): specify editable canvas document v1`
- RED 证据：TS 契约测试因 `./canvas` 不存在而解析失败；Python 测试因 `app.schemas.canvas` 不存在而收集失败。
- GREEN 与回归：Canvas TS 3 passed、Python 3 passed；完整前端 13 passed、完整后端 35 passed；contracts strict TypeScript check 与前端 build 成功。
- 结果：共享 fixture 确定 schema_version 1.0、IP Studio UUID 资产/版本引用、标题动态字段、每页冻结品牌版本、元素 transform/crop 和 snake_case 字段；消息方向由 sender 与 self participant 相等性派生。
- 限制：此任务负责静态结构验证；资产 UUID 是否真实存在及是否归属当前 IP 将在服务端保存任务中二次校验。

#### Task 4 交付记录

- 提交：`feat(editor): render fixed shell and editable manga canvas`
- RED 证据：新增编辑器测试在 `ComicEditor` 尚未实现时因模块导入失败。
- GREEN 与回归：编辑器专项 2 passed；完整前端 15 passed；Vite build 与 contracts strict TypeScript check 成功。后端当前回归为 35 passed。
- 结果：品牌静态层不可选/不可拖动；标题和 EP 编号仅能在属性栏改文字；相同品牌配置重复渲染固定坐标；画格内容独立 Konva 节点并按 z_index 排序，画格容器剪裁；支持图片、原生文字、气泡、聊天消息、形状、贴纸、旋转/缩放/拖动、网格/安全区和页面切换。缩减布局将丢内容时显示错误并拒绝修改。
- 限制：组件现可由 Episode 工作台消费；Episode 文档加载/保存及撤销命令在 Task 5/阶段 03 接入。

#### Task 5 交付记录

- 提交：`feat(editor): add PPT-style layers with safe history`
- RED 证据：前端命令测试因 `commands` 模块缺失失败；后端文档 API 在实现前返回 404。新增保存期间继续编辑的回归测试在修复前观察到第二个旧 revision 请求并行发出。
- GREEN 与回归：`uv run --project services/api pytest -v`（39 passed）；`pnpm --filter @ip-studio/web test`（21 passed）；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0005_documents` upgrade、`alembic check`（无新差异）、downgrade base、upgrade head 均通过。
- 结果：文本/聊天消息双击 DOM 编辑，原生文字、气泡、消息与图片保持独立图层；图层命令仅修改白名单字段、锁定元素拒改；50 步 undo/redo；1.5 秒防抖自动保存并串行排队编辑；API 以 `base_revision` CAS 原子写入快照，冲突返回 409；按 workspace/IP 检查批准的品牌、风格及图片引用；可读 revision 快照并恢复为新 revision。
- 限制：本机 Docker daemon 未运行且没有 PostgreSQL 二进制，故未执行 PostgreSQL runtime smoke test；SQLite API 测试和 Alembic 生命周期已通过。

## 阶段 03：剧本分镜与生产

- [x] Task 1：剧本 Revision、场景、分镜持久化
- [x] Task 2：参考资产打包与无字提示词
- [x] Task 3：浏览器拖拽、粘贴与候选入库
- [x] Task 4：候选审核、替换单格与可复用素材

#### Task 1 交付记录

- 提交：`feat(story): add versioned scripts and storyboard`
- RED 证据：新增服务端测试在实现前因剧本路由返回 404；前端测试因 `ScriptEditor` 不存在而无法解析导入。
- GREEN 与回归：`uv run --project services/api pytest -v`（42 passed）；`pnpm --filter @ip-studio/web test`（25 passed）；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0006_scripts` upgrade、`alembic check`（无新差异）、downgrade base、upgrade head 均通过。
- 结果：Episode 剧本修订只追加；Markdown 与结构化场景分开保留；场景/对白/镜头卡保存角色版本、背景素材、镜头动作和无字提示；引用角色/背景必须同 IP 且已批准。对白差异先预览，用户确认后以新文档 revision 同步已有聊天消息/气泡文字；不改图片、品牌和其他图层。前端已提供剧本编辑、分镜卡列表和确认预览组件/API。
- 限制：生产工作台导航和 Browser/Playwright 演示会在后续任务接入；PostgreSQL runtime smoke test 因当前环境无 Docker daemon / PostgreSQL 二进制未运行，SQLite API 与迁移全生命周期已验证。

#### Task 2 交付记录

- 提交：`feat(production): add generation prompts and reference bundles`
- RED 证据：后端测试因提示构建服务尚不存在而无法收集；前端测试因 `GenerationTaskCard` 尚不存在而无法解析导入，均由缺少功能实现触发。
- GREEN 与回归：完整后端 `uv run --project services/api pytest -q`（45 passed）；完整前端 `pnpm --filter @ip-studio/web test`（29 passed）；GenerationTask Zod 合同 2 passed；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0007_generation_tasks` upgrade、`alembic check`（无差异）、downgrade base、再次 upgrade，全部通过。
- 结果：生成任务冻结脚本修订、Panel、精确批准角色/画风/素材版本、提示词和参考元数据；对白文本不会送入提示词；只接受当前可用的 ChatGPT Web 人工模式；跨 IP 和未批准版本返回拒绝；ZIP 只打包冻结的批准图像 Blob，校验 SHA-256 并限制总大小 100 MiB；任务初始为 `prepared`，人工确认后变为 `waiting_manual_generation`。前端提供冻结版本、复制提示词、下载 ZIP 和状态切换任务卡。
- 限制：PostgreSQL runtime smoke test 因 Docker daemon 未运行且无本地 PostgreSQL 二进制未执行。工作台导航、候选导入和审核继续按阶段 03 后续任务落地。

#### Task 3 交付记录

- 提交：`feat(production): import ChatGPT output as candidate assets`
- RED 证据：候选 API 实现前返回 404；前端因 `ImportAssetDropzone` 模块缺失而无法解析测试导入。
- GREEN 与回归：完整后端 `uv run --project services/api pytest -q`（47 passed）；完整前端 `pnpm --filter @ip-studio/web test`（34 passed）；GenerationCandidate Zod 合同 3 passed；`pnpm --filter @ip-studio/web build` 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0008_generation_candidates` upgrade、`alembic check`（无差异）、downgrade base、再次 upgrade，全部通过。
- 结果：浏览器可拖放/选择图片、粘贴或通过用户点击触发读取剪贴板；仅接收 PNG/JPEG/WebP 和 25 MiB 内图片；未选画格或当前画格不等于任务冻结 Panel 时不上传、不关联；任务须进入人工生成状态。API 要求候选资产与任务同 workspace/IP、资产版本仍为 candidate；候选绑定到任务冻结的 Panel，任务转为 `asset_imported`，素材通过 `AssetLink` 固定以免误删，重复绑定返回 409。
- 限制：PostgreSQL runtime smoke test 因本机 Docker daemon 未运行且无 PostgreSQL 二进制未执行；候选审核、接受/拒绝与画格替换属于下一 Task。

#### Task 4 交付记录

- 提交：`feat(production): add candidate review and panel replacement`
- RED 证据：审核路由和前端组件缺失时专项测试按预期失败；补充重复拒绝回归断言后，首次观察到服务异常因路由捕获了另一组异常类而抛出 500，随后统一异常类型并验证返回 409。
- GREEN 与回归：候选审核后端专项 2 passed；完整后端 `uv run --project services/api pytest -q`（49 passed）；完整前端 `pnpm --filter @ip-studio/web test`（37 passed）；GenerationCandidate 合同测试 3 passed；Vite/TypeScript build 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0009_candidate_reviews` upgrade、`alembic check`（无差异）、downgrade base、再次 upgrade 全通过。
- 结果：管理员可在同 IP 候选库查看审核历史、预览、批准并加入可复用素材或填写原因拒绝；审核人、时间与状态一同冻结，重复审核返回 409，拒绝素材归档且不能再次绑定，通用素材审批接口不能绕过候选审核。编辑器替换只对已解锁画格中的目标 image/sticker 发出白名单 `replace_image` 命令，品牌、标题和台词保留原值。整页位图继续标注为不可逐笔拆分的参考图。
- 限制：PostgreSQL runtime smoke test 因本机 Docker daemon 未运行且无 PostgreSQL 二进制未执行；SQLite API 测试和 Alembic 全生命周期已通过。

## 阶段 04：Codex ImageGen 集成

- [x] Task 1：Codex 环境能力自检 PoC
- [x] Task 2：本地任务 Adapter 与图片安全回流
- [x] Task 3：结构化 CanvasPatch 白名单与授权校验
- [ ] Task 4：用户确认、应用 Patch 与降级体验

#### Task 1 交付记录

- 提交：`feat(codex): probe real local imagegen capabilities`
- RED 证据：能力模块实现前测试因 `app.codex` 不存在而失败；显式探测路由实现前，管理员 POST 测试因调用器缺失而失败。
- GREEN 与回归：能力专项 `uv run --project services/api pytest services/api/tests/test_codex_capabilities.py -v`（9 passed）；完整后端 `uv run --project services/api pytest -q`（58 passed）；`git diff --check` 通过。
- 真实探测：当前环境 `/opt/homebrew/bin/codex`，版本 `codex-cli 0.162.1`；`codex login status` 有效；stdio App Server 完成初始化并报告 `imageGeneration=true`；本轮一次原生 ImageGen 生成得到 1254×1254 PNG，Pillow 验证与完整解码成功。具体证据记录在 `docs/architecture/codex-capability-matrix.md`。
- 结果：受管理员保护的 GET 只读查询 Codex 登录与 App Server provider 能力；provider 声明不会单独标为可用；管理员显式 POST 才会运行原生生成探测，检查工具事件、受限临时输出路径、PNG 解码及尺寸/大小，结果只缓存绑定当前 CLI 路径/版本，不会导入项目资产。探测失败时仍保留 ChatGPT Web 人工生成入口。
- 限制：真实 ImageGen 调用期间出现模型目录与 hosted tool 通道瞬时超时，随后成功；API 每次显式探测若再次遇到此类超时会如实报告不可用。本机 PostgreSQL runtime 限制沿用阶段 01 记录。

#### Task 2 交付记录

- 提交：`feat(codex): execute gated imagegen and import candidates`
- RED 证据：能力结果安全回流的测试先因 `app.codex.image_result` 和 `app.api.codex_runs` 缺失而失败；输出越界单测在路径校验实现后先通过。
- GREEN 与回归：Codex run/Adapter 专项 `uv run --project services/api pytest services/api/tests/test_codex_runs.py -v`（6 passed）；完整后端（64 passed）；完整前端（42 passed）；Codex 与 Generation Zod 合同（5 passed）；Vite/TypeScript build 成功；`git diff --check` 通过。
- 迁移验证：SQLite `0010_codex_runs` upgrade、`alembic check`（无差异）、downgrade base、再次 upgrade 全部通过。
- 结果：管理员显式启动任务，服务端重新核验通过真实 ImageGen 的 Codex CLI 路径与版本；CLI 通过独立受限临时目录执行，只附加冻结参考包，校验 SHA-256、ZIP 路径、原生 ImageGen 事件、输出路径、PNG/JPEG 魔数、完整解码和大小/像素限制。输出来源记为 `codex_native`，与当前任务原子关联为 `pending_review` 候选；生成失败不推进任务、不创建候选。状态支持排队、运行、候选就绪、失败，具备超时和管理员取消；数据库约束阻止同任务并发 run 和跨任务候选绑定。前端只有 E2E 探测成功后开放本机生图入口，ChatGPT Web 手动生图与导入始终保留。
- 限制：本任务通过模拟 CLI 子进程事件验证 Adapter，不再次触发真实生图；真实原生 ImageGen 的 CLI/工具/图片能力探测证据沿用 Task 1。PostgreSQL runtime smoke test 仍受本机 Docker/PostgreSQL 服务不可用限制；SQLite migration 生命周期与 API 集成已验证。

#### Task 3 交付记录

- 提交：`feat(codex): validate scoped proposed canvas patches`
- RED 证据：后端测试在 Patch validator 模块缺失时因预期导入错误失败；合同测试在 `canvas-patch.ts` 尚不存在时无法导入。
- GREEN 与回归：后端 Patch 专项 8 passed；完整后端 72 passed；完整前端 44 passed；CanvasPatch/Codex/Generation 合同 7 passed；Vite/TypeScript build 和 `git diff --check` 通过。
- 结果：新增严格的 Pydantic 与 Zod Patch 协议，只有 `set_text`、`set_transform`、`replace_image_asset`、`insert_element`、`remove_element` 五类操作；最多 50 项。校验 workspace/IP/Episode/Document/base revision、元素 ID 和类型、锁定元素/面板框、Transform 数值与同 IP 已批准素材引用。逐项生成隔离的预览副本，验证不改变输入文档，也没有数据库写入路径；任意 SQL、命令、路径或额外字段均无法通过协议解析。
- 限制：Patch 数据验证已完成；向本机 Codex 请求提案、持久化待审批记录、人工批准/拒绝与 CAS 应用在 Task 4 实现。

## 阶段 05：导出与验收

- [ ] Task 1–5：见 `2026-10-14-05-export-and-acceptance.md`
