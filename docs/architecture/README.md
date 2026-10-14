# V1 参考架构与数据契约

> 本目录描述**待实现**架构，不代表仓库已有可运行服务。主需求：[`docs/product/PRD-v1.md`](../product/PRD-v1.md)。

## 边界图

```text
React/Vite (apps/web)  ---- typed HTTP ---->  FastAPI (services/api)
   |  Konva scene graph                         | Pydantic/SQLAlchemy/Alembic
   |  Zustand commands + Zod                     | PostgreSQL + BlobStorage(local)
   |  Brand fixed + Episode content              | generation tasks + revision guard
   |                                             |
   | optional local Codex Bridge <-----> Codex App Server / ImageGen (probe first)
   | manual fallback: ChatGPT copy/paste ---> asset upload
   |
   +-- PNG rendering / PPTX export (PptxGenJS, tests prove editability)
```

## 责任边界

- `apps/web/src/features/ips/`：IP 列表与详情；`assets/`：资产工作台；`editor/`：画布、图层、命令；`templates/`：品牌/格子模板；`production/`：剧本、任务；`codex/`：状态与任务 UI。
- `services/api/app/api/`：所有 API；`models/`：SQLAlchemy；`schemas/`：Pydantic；`services/`：业务检查；`storage/`：blobs；`codex/`：探测、受限任务、结果导入；`export/`：ZIP/PNG 及状态。
- `packages/contracts/src/`：Zod `CanvasDocumentV1`、`BrandTemplateV1`、`CanvasPatchV1`；`fixtures/`：与 Python 共享的 JSON fixture。
- `tests/e2e/`：Playwright 真实浏览器链路；包含《人间卡顿局》匿名可分发模拟素材，不上传未经确认可分享的角色图。

## 稳定领域关系

```text
Workspace → IP → (Character → CharacterVersion)
                → (Style → StyleVersion)
                → (BrandTemplate → BrandTemplateVersion)
                → (Series → Episode → Page → Panel → CanvasElement)
                         └→ ScriptRevision / DocumentRevision / ExportJob
Workspace → Asset → AssetVersion → Blob(sha256)
            AssetVersion <— Page/Panel/CanvasElement/reference
GenerationTask → [codex_native | chatgpt_web | asset_only] → Candidate AssetVersion
```

- **版本**：批准的 CharacterVersion/StyleVersion/BrandTemplateVersion/AssetVersion 不允许修改 payload。
- **渲染**：BrandTemplateVersion 的锁定背景 + Episode/Panel/Layout 内容 + Brand 前景及动态标题。Title/EP number 动态文本只修改值、不修改版式。
- **一致性**：每页绑定 `brand_template_version_id`，每个 Element 的 `asset_version_id` 指向已存在、可访问的版本。
- **事务**：`PUT /api/v1/episodes/{id}/document` 请求带 `base_revision`，服务端 CAS 更新，冲突返回 409；恢复旧版需新 revision。
- **权限**：单管理员也必须校验 workspace 与 IP 归属。共享资源必须显式建立共享关系。
- **Codex**：只可读特定资源并生成建议 / 候选图片，不允许无审查任意写文件或数据库。

## 前后端数据契约

- JS / Python 一律使用 snake_case 的网络 JSON 键（`schema_version`, `asset_version_id`, `base_revision`）。
- 图层类型：`image`, `text`, `speech_bubble`, `thought_bubble`, `chat_message`, `shape`, `sticker`, `panel_frame`。
- 绝对坐标使用“文档像素”，裁切区域使用 0～1 归一化坐标，旋转角度单位为 degree。
- `chat_message` 方向由 `sender_id === self_participant_id ? right : left` 派生；手动方向覆盖要警告。
- 每个数据修改必须能生成 `document_revision`；画布内部的缩放/选中等临时 UI 状态不进入工程 JSON。
- 生成任务：`mode=codex_native|chatgpt_web|asset_only`，候选图经人工审核才进入正式画格引用。
- 文件限制建议：PNG/JPEG/WebP，单文件不超过 25MB，后端对魔数、解码、像素尺寸、SHA256 做校验。
- ZIP 导入须拒绝 `../`、绝对路径、符号链接与过大解压数据；PPTX 导出需验证各对象真正独立。

## 决议与暂定

| 事项 | 本轮决定 | 原因 |
|---|---|---|
| 起步技术 | React+TS+Vite、Konva、Zustand、FastAPI、PostgreSQL | 精简、可测试 |
| 画布唯一源 | 结构化 JSON，图片引用 AssetVersion | 编辑可恢复 |
| 图片来源 | Codex ImageGen 经 PoC 验证优先；手动始终可用 | 兼顾成本与可靠性 |
| 资源存储 | local BlobStorage interface，未来可接 S3 | 降低 V1 成本 |
| Jellyfish | 不 Fork | 偏向完整视频生产流，非资产编辑核心 |
| PPTX | PptxGenJS：文字、形状、图片对象分别生成 | 符合局部可编辑 |
| 发布运营 | V2+ | 不纳入 V1 验收 |

## Agent 不可擅自更改的事项

请勿自行新增 OAuth 平台发布、付费图像 API、全自动视频生成、账号矩阵运营、多人协作。设计变化先在 PRD 与 spec 记录后再计划和实现。
