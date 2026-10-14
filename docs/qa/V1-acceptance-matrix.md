# IP Studio V1 验收矩阵

日期：2026-10-14（Asia/Shanghai）
基线：[PRD V1 Definition of Done](../product/PRD-v1.md#9-验收标准definition-of-done)

状态只记录有代码或可复演步骤支持的结果。`BLOCKED` 项仍是发布门槛；不能把本机没有运行的 PostgreSQL 恢复演练或 Codex 原生 ImageGen API 演练算作通过。

| AC | 状态 | 验收证据与复演入口 |
|---|---|---|
| AC-01 | PASS | 三个 IP 各自上传图片并按 `ip_id` 筛选：[test_three_ips_keep_their_uploaded_assets_separate](../../services/api/tests/test_assets.py)、[AssetLibrary IP 筛选](../../apps/web/src/features/assets/AssetLibrary.test.tsx)。 |
| AC-02 | PASS | 已批准角色不可覆写，须派生新版本：[test_approved_character_is_immutable_and_can_be_derived](../../services/api/tests/test_bibles.py)。 |
| AC-03 | PASS | EP01 E2E 替换单格图片并比较其它格、对白及几何；另有 [ReplacePanelImage 测试](../../apps/web/src/features/editor/ReplacePanelImage.test.tsx)。 |
| AC-04 | PASS | [EP01/EP02 浏览器验收](../../tests/e2e/ip-studio.spec.ts)：朋友“在吗？”在左，卡仔“不在。”在右；API fixture 另作回读。 |
| AC-05 | PASS | 同一浏览器验收连续修改 10 次中文、撤销/重做、保存、刷新并检查 PPTX XML 中文文本。 |
| AC-06 | PASS | Shift/Ctrl/⌘ 多选同一画格图层；一次整体移动产生一个 `set_transforms` 命令，一次 Undo 恢复整组：[commands.test.ts](../../apps/web/src/features/editor/commands.test.ts)、[EP01 E2E](../../tests/e2e/ip-studio.spec.ts)。 |
| AC-07 | PASS | EP01 浏览器流程保存后刷新，并确认最新文字重新载入：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)。 |
| AC-08 | PASS | 两标签页同时打开相同 revision；赢家保存，过期标签收到 409 且重新载入赢家内容：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)、[test_document_conflict_returns_409_and_keeps_the_winning_revision](../../services/api/tests/test_document_conflicts.py)。 |
| AC-09 | PASS | 素材以批准位图图层进入画布；候选审核页明确说明旧扁平图片只作参考，不会拆成笔触图层：[CandidateReview.tsx](../../apps/web/src/features/production/CandidateReview.tsx)、[ComicEditor.tsx](../../apps/web/src/features/editor/ComicEditor.tsx)。手动复演步骤见 [V1-manual-runbook.md](V1-manual-runbook.md)。 |
| AC-10 | PASS | 浏览器串联结构化剧本、分镜卡、冻结 ChatGPT Web 任务、人工状态、上传候选和批准；提示词及参考包组件测试：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)、[GenerationTaskCard.test.tsx](../../apps/web/src/features/production/GenerationTaskCard.test.tsx)。 |
| AC-11 | PASS | 十页浏览器导出逐页检查上传 PNG 为 1080×1440，ZIP 检查 10 个有序文件：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)；单页原尺寸/品牌版本测试：[exportPng.test.ts](../../apps/web/src/features/export/exportPng.test.ts)。 |
| AC-12 | PASS | 浏览器下载 PPTX 并检查独立 `<p:pic>`、`<p:sp>` 与中文对象；阶段 Task 3 另用 LibreOffice 成功解析并转 PDF，记录见 [执行进度](../superpowers/plans/PROGRESS.md#task-3-交付记录)。 |
| AC-13 | PASS | [工程 ZIP 往返与安全测试](../../services/api/tests/test_project_bundle.py)覆盖 hash、引用、跨 IP 重映射及恶意路径；manifest 合同测试在 `packages/contracts/src/project-manifest.test.ts`。 |
| AC-14 | PASS | 删除被引用素材会拒绝并保留 Blob：[test_delete_used_asset_blocked](../../services/api/tests/test_assets.py)。 |
| AC-15 | PASS | 恢复旧版本会新建 revision 且保留旧历史：[test_restore_creates_a_new_revision_without_erasing_history](../../services/api/tests/test_document_conflicts.py)。 |
| AC-16 | PASS | 输入 160 个汉字会出现可见溢出提示；估算 helper 单测与浏览器测试：[textOverflow.test.ts](../../apps/web/src/features/editor/textOverflow.test.ts)、[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)。 |
| AC-17 | PASS | 假 PNG、MIME 不匹配、超大图片和像素上限均拒绝；验证服务器未创建残缺 Asset/Blob：[test_assets.py](../../services/api/tests/test_assets.py)。 |
| AC-18 | PASS | PostgreSQL 17.11 上执行 Alembic upgrade/check/downgrade/upgrade/check；另真实 `pg_dump` + Blob tar 备份后删除并恢复数据库和 Blob，恢复后管理员登录、图片内容逐字节一致、工程 ZIP 再导出成功。演练记录见 [backup-restore.md](../deployment/backup-restore.md#completed-test-run-2026-10-14)。 |
| AC-19 | PASS | Chromium 加载 30 个画布元素后可选图层、编辑中文并执行组位移；在人工 ChatGPT 模式下完成，没有调用外部 AI API：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)。这覆盖交互回归，不代表帧率基准测试。 |
| AC-20 | PASS | 无 Codex ImageGen 时，已有素材工作台、画布编辑和导出仍可用；人工模式 E2E 显示 ChatGPT Web 的提示词、参考包及导入入口。 |
| AC-21 | PASS | EP01/EP02 精确引用同一批准模板版本，动态标题不同；API 回归、[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts) 与 [Playwright 截图](evidence/ep02-editor.png)。 |
| AC-22 | PASS | 固定品牌图层不可选中/拖动；批准模板静态元素锁定测试：[ComicEditor.test.tsx](../../apps/web/src/features/editor/ComicEditor.test.tsx)、[test_locked_logo_edit_denied](../../services/api/tests/test_templates.py)。 |
| AC-23 | PASS | 已批准 Brand Template 不可覆写，派生版本不会改写已有文档引用：[test_brand_immutable_after_approval](../../services/api/tests/test_templates.py)、[test_episode_document_cannot_silently_migrate_brand_version](../../services/api/tests/test_document_conflicts.py)。 |
| AC-24 | PASS | 浏览器将 Codex ImageGen 状态设为 unsupported，仍可启动 ChatGPT Web 人工任务、导入并审核候选：[ip-studio.spec.ts](../../tests/e2e/ip-studio.spec.ts)；Codex 文案单测：[CodexAssistant.test.tsx](../../apps/web/src/features/codex/CodexAssistant.test.tsx)。 |
| AC-25 | BLOCKED | 在真实 FastAPI/PostgreSQL session 对管理员调用 `POST /api/v1/codex/capabilities/probe`：provider 声明 `imageGeneration=true`，但 CLI 未记录可验证的原生 ImageGen 事件或 PNG；已有尝试分别遇到 exit code 1 与无原生事件。随后在临时 SQLite API 实例发起的一次探测未返回报告，因等待无响应而被人工中断；结果未知，不作为成功或失败证据。API 未验证能力，因此拒绝启动 native run，没有产生候选。OpenAI 当前 ChatGPT-plan App Server 文档称 Responses 路径不支持 Image Generation；这与探测失败相符，但因应用不读取认证凭据，不能视为已确认根因。探测证据、边界与官方资料见[能力矩阵](../architecture/codex-capability-matrix.md)；ChatGPT Web 人工路径持续可用。 |
| AC-26 | PASS | 跨 IP Patch 与跨 IP 图片替换被拒绝，源文档无副作用：[test_cross_ip_patch_is_denied](../../services/api/tests/test_codex_patches.py)、[test_cross_ip_asset_replacement_is_denied](../../services/api/tests/test_codex_patches.py)。 |

## 复演命令

```bash
pnpm --filter @ip-studio/web test
pnpm --filter @ip-studio/web test:e2e
pnpm --filter @ip-studio/web build
uv run --project services/api pytest -q
```

**发布状态：BLOCKED。** AC-25 是矩阵内唯一 `BLOCKED` 验收项；待兼容的本机 Codex 原生 ImageGen 在 IP Studio API 管理员探测中成功生成并验证 PNG，再完成服务端候选回流演练后复核。发布清单中远端 GitHub Actions、发布版本验证日志和生产配置检查也尚未完成。
