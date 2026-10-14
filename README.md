# IP Studio

面向原创漫画 IP 的**数字资产管理、可编辑创作与模板化出版工作台**。

> 状态：V1 计划内功能代码与自动化回归已完成。真实 PostgreSQL + Blob 恢复演练已通过；当前发布只受 IP Studio API-owned Codex ImageGen 探测/候选回流阻断，逐项状态见 [V1 验收矩阵](docs/qa/V1-acceptance-matrix.md)。

## V1 定位

- 管理多个 IP 的 Character Bible、Style Bible、场景、道具、参考图及版本。
- 使用**固定 IP 品牌模板**制作漫画：外框、底色、徽标、固定装饰和版面风格受控；每期编辑标题、分镜、台词与剧情内容。
- 像 PPT 一样编辑多页画布中的角色图片、文字、聊天气泡、形状及图层；生成图像始终是位图素材，不能无损拆成矢量层。
- 本机 Codex + ImageGen 仅在管理员显式能力探测成功后启用；始终保留用户在 ChatGPT Web 手动生图后的导入闭环。
- 导出 PNG 图组、完整可恢复工程 ZIP 与部分可编辑 PPTX。

第一版**不包含**视频生成、小红书自动发布、多账号数据运营、模型训练或多租户 SaaS。

## 必读文档

1. [产品 PRD V1（唯一需求基线）](docs/product/PRD-v1.md)
2. [设计说明（Superpowers Spec）](docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md)
3. [开发任务索引](docs/superpowers/plans/README.md)
4. [架构与数据契约](docs/architecture/README.md)
5. [Agent 开发约定](AGENTS.md)

## 验证与部署

先按[本地开发指南](docs/deployment/local-development.md)安装依赖并启动 PostgreSQL、API 和 Web。常用验证入口为 `bash scripts/verify-v1.sh`；CI 另外运行 PostgreSQL migration lifecycle 和 Playwright Chromium E2E。备份/恢复和发布门槛分别见[备份恢复 Runbook](docs/deployment/backup-restore.md)与[V1 发布检查表](docs/qa/V1-release-checklist.md)。

需求基线、架构与阶段计划仍是开发/维护的权威入口：[产品 PRD V1](docs/product/PRD-v1.md)、[设计说明](docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md)、[开发任务索引](docs/superpowers/plans/README.md)、[架构与数据契约](docs/architecture/README.md)。

参考方法：<https://github.com/obra/superpowers>

## 目录规划

```text
apps/web/              React + Vite + TypeScript UI
services/api/          FastAPI + PostgreSQL + Blob storage
packages/contracts/    TypeScript Zod API/document contracts
tests/e2e/             Playwright acceptance flows
docs/                  Product, architecture, plans, QA, deployment
scripts/               Local verification entry points
```

**原则：先保证资产和工程格式长期可维护，再增加生成能力。**
