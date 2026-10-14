# IP Studio — Agent 开发约定

本项目处于 **design-ready、not implemented** 状态。请勿声称功能已实现。

## 权威材料与阅读顺序

1. `docs/product/PRD-v1.md`：唯一规范性需求基线
2. `docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`：边界、模块与权衡
3. `docs/architecture/README.md`：目录、协议、数据契约
4. `docs/superpowers/plans/README.md`：执行顺序与任务入口
5. 当前阶段的 implementation plan（切勿跳过）

如文档冲突，以最新正式 PRD 为准；实现发现重大歧义时在 PR 中说明，不要静默改变产品范围。

## Superpowers 工作流（必须）

- 使用已安装的 <https://github.com/obra/superpowers> 技能：
  - 需求有变时先走 `superpowers:brainstorming`，获得设计确认后更新 spec；
  - 开发前读取 `superpowers:writing-plans` 格式；
  - 执行时选择 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`；
  - 每个任务遵循 **RED → GREEN → REFACTOR → VERIFY → COMMIT**；
  - 提交前使用 `superpowers:verification-before-completion`，重大变更配合 code review。
- 遵守依赖顺序；每项任务原则上一份 PR，或者同一阶段少量审查可控的 PR。
- 任何当前未通过的测试不得谎称通过。需要权限、工具、Codex/ImageGen 时先能力探测；无权限就记录 blocked 并完成可独立验证的回退路径。
- 任务进度建议记录 `docs/superpowers/plans/PROGRESS.md`（由首个执行 Agent 创建）；每次 PR 更新完成的任务编号、测试命令和产物链接。

## 不可违反的产品不变量

- 单工作室管理员、支持多 IP；**不实现 V1 小红书账号运营与自动发布**。
- 同一 IP 品牌外壳（底色/装饰/Logo/标题位置/页脚）锁定；仅模板编辑模式可创建新版本。标题**文字**和漫画内容可改。
- 角色/风格/品牌批准版本不可原地覆写；作品冻结引用精确版本。
- 生图素材是位图；**不能虚构 Photoshop/PPT 原生笔触可编辑性**。所有中文、聊天消息和气泡用独立原生对象绘制。
- 本机 Codex ImageGen 仅在实际调用后确认；**默认要求回退到在线 ChatGPT 人工导入**。不得使用 ChatGPT 私有 API/Cookie 或将 Plus 假设成开发者 API 额度。
- Codex 修改数据必须白名单 Patch、跨 IP 授权校验、base revision 检查、人工批准。**禁止 Codex 任意 SQL 或无审批文件覆盖。**
- 测试 EP01/EP02：两期同模板外壳不漂移；EP01 中朋友消息“在吗？”在左，卡仔“不在。”在右。
- 工程 JSON + 引用素材是唯一权威源；PNG、PPTX 均是导出制品。PPTX 的单张位图不可逐笔修改。
- 不加入视频、付费图片 API、多用户协同、自动发帖或重型外部漫剧平台依赖。

## 计划内代码目录（由任务创建）

```text
apps/web/              React/Vite/TypeScript 前端
services/api/          FastAPI + PostgreSQL + BlobStorage
packages/contracts/    TypeScript Zod JSON 协议和 fixture
tests/e2e/             Playwright 跨端验收
docs/                  产品/架构/Superpowers 设计与执行计划
```

## 交付约定

- 每项 PR：对应 Task ID、变更清单、测试证据、已知风险、截图或 E2E 演示（若涉及 UI）。
- 后端 `pytest`、前端 `vitest`、端到端 `playwright` 为计划内测试体系；命令和配置在 M0 Task 1 实现前**并不存在**，不要先运行并假报结果。
- 用户已有 ChatGPT 订阅，但订阅能力和开发者 API 计费、Codex 环境工具暴露各自独立。
