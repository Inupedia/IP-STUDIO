# IP Studio

面向原创漫画 IP 的**数字资产管理、可编辑创作与模板化出版工作台**。

> 状态：产品设计 / 开发计划已确立；**尚未实现业务代码**。

## V1 定位

- 管理多个 IP 的 Character Bible、Style Bible、场景、道具、参考图及版本。
- 使用**固定 IP 品牌模板**制作漫画：外框、底色、徽标、固定装饰和版面风格受控；每期编辑标题、分镜、台词与剧情内容。
- 像 PPT 一样编辑多页画布中的角色图片、文字、聊天气泡、形状及图层；生成图像始终是位图素材，不能无损拆成矢量层。
- **优先验证本机 Codex + ImageGen** 完成生图、版本管理、自动入库；如当前环境不支持，则保留在线 ChatGPT 生图后的粘贴/导入闭环。
- 导出 PNG 图组、完整可恢复工程 ZIP 与部分可编辑 PPTX。

第一版**不包含**视频生成、小红书自动发布、多账号数据运营、模型训练或多租户 SaaS。

## 必读文档

1. [产品 PRD V1（唯一需求基线）](docs/product/PRD-v1.md)
2. [设计说明（Superpowers Spec）](docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md)
3. [开发任务索引](docs/superpowers/plans/README.md)
4. [架构与数据契约](docs/architecture/README.md)
5. [Agent 开发约定](AGENTS.md)

## 开发交接

从 [开发任务索引](docs/superpowers/plans/README.md) 的第 01 阶段开始，严格按依赖顺序推进。每个任务依照 `superpowers:writing-plans` 的 TDD、验证与提交要求执行，并使用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`。

参考方法：<https://github.com/obra/superpowers>

## 目录规划

```text
IP-STUDIO/
├── README.md
├── AGENTS.md
├── .gitignore
├── docs/
│   ├── product/PRD-v1.md
│   ├── architecture/README.md
│   └── superpowers/
│       ├── specs/2026-10-14-ip-studio-v1-design.md
│       └── plans/
│           ├── README.md
│           ├── 2026-10-14-01-foundation-and-asset-registry.md
│           ├── 2026-10-14-02-brand-templates-and-canvas.md
│           ├── 2026-10-14-03-storyboard-and-production.md
│           ├── 2026-10-14-04-codex-imagegen-integration.md
│           └── 2026-10-14-05-export-and-acceptance.md
└── (apps/, packages/, tests/：由各阶段任务创建，不预置空结构)
```

**原则：先保证资产和工程格式长期可维护，再增加生成能力。**
