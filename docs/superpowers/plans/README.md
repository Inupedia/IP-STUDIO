# IP Studio V1 — Superpowers 实施计划索引

> 编排依据：[Superpowers writing-plans](https://github.com/obra/superpowers/blob/main/skills/writing-plans/SKILL.md)
> 需求权威：[`docs/product/PRD-v1.md`](../../product/PRD-v1.md)
> 设计：[`docs/superpowers/specs/2026-10-14-ip-studio-v1-design.md`](../specs/2026-10-14-ip-studio-v1-design.md)

以下文件是原始实施计划，描述各阶段的 Task / Interfaces / RED–GREEN–COMMIT 要求；实际完成状态以 [`PROGRESS.md`](PROGRESS.md) 和 QA 验收/发布检查表为准。阶段 01–04 与阶段 05 的 Task 1–4 已完成；阶段 05 Task 5 的独立只读静态审查已完成，PR 合并、正式版本制品和实际生产主机验证仍未完成。

| 顺序 | 实施计划 | 核心交付 | 依赖 |
|---|---|---|---|
| 01 | [工程与资产版本](2026-10-14-01-foundation-and-asset-registry.md) | monorepo、IP CRUD、资产仓库、角色/画风冻结 | 无 |
| 02 | [品牌模板与画布](2026-10-14-02-brand-templates-and-canvas.md) | 模板 v1、4/6/8 格、PPT 式编辑、撤销和保存 | 01 |
| 03 | [剧本分镜与生产](2026-10-14-03-storyboard-and-production.md) | Episode、提示词、人工 ChatGPT 回退、候选图入库 | 01、02 |
| 04 | [Codex ImageGen 集成](2026-10-14-04-codex-imagegen-integration.md) | 能力自检、本机真实生成、受限 Patch、人工回退 | 01、02、03 |
| 05 | [导出与发布验收](2026-10-14-05-export-and-acceptance.md) | PNG、ZIP、PPTX、EP01/EP02 E2E、备份 | 01–04；核心导出可并行 |

## Agent 接力流程

1. 先读 `AGENTS.md`、PRD、Spec、Architecture，再读一个当前计划。
2. 从该计划的 **Task 1** 开始，不得跳任务写一大块“完成全部”代码。
3. 采用 `superpowers:subagent-driven-development` 或 `superpowers:executing-plans`；如缺少安装，用项目文档的 TDD/复核方法执行，不假称已调用 Skill。
4. 每项任务先写失败测试，再最小实现，再运行测试；只提交可验证的代码。若用户已授权可创建 PR，建议一任务一 PR。
5. 将实际 commit、测试命令/结果、阻塞点记录在后续创建的 `docs/superpowers/plans/PROGRESS.md`。
6. 由另外一个 Agent 接手时，首先核对 GitHub 上**真实已合并的变更**，不要依赖上一位 Agent 自述。
7. 不在此仓库拷贝/复刻 Superpowers 的 skill 文件；本仓库只存符合该工作流的设计与实施计划。

## Review gates

- 每阶段结束都运行其测试命令并做对应功能走查。
- 每个计划的 `Global Constraints` 与 `Review Focus` 是审查强制项。
- 如发现 Codex ImageGen 不可用，记录能力不支持并验证完整人工回退；**不要停止其他任务**。
- 最终发布前必须逐条证明 PRD AC-01～AC-26，未通过项不得标记完成。
