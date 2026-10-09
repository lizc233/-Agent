# 袋鼠智服 Agent 系统升级工作流

## 升级目标

将当前“任务规划—订单查询—RAG—回答”的单链路，升级为具备技能选择、并行专业 Agent、长期记忆、售后工单状态变更、证据审核和 MCP 工具协议的客服 Agent 系统。

## 最终工作流

```text
用户问题
  ↓
Supervisor：结构化任务规划、技能选择、依赖分析
  ↓
并行专业 Agent
  ├─ Order Agent：查询当前用户订单事实
  ├─ Policy Agent：bge-m3 检索客服规范
  ├─ Memory Agent：召回当前用户相关会话与历史工单
  └─ Risk Agent：越权、食品安全、恶意请求和转人工判断
  ↓
Evidence Reviewer：交叉校验订单、规则、记忆与风险结论
  ↓
Case Agent：创建工单、补充证据、推进状态或查询进度
  ↓
DeepSeek：仅依据工具结果和可信证据生成回答
  ↓
回答 / 订单选择 / 请求材料 / 创建工单 / 拒答 / 转人工
```

## 第一阶段：工单状态机与长期记忆

- 新增 `after_sales_case`、`case_event`、`conversation_session`、`conversation_memory` 表。
- 工单状态限定为 `WAITING_EVIDENCE`、`PENDING_REVIEW`、`SOLUTION_PROPOSED`、`CLOSED`、`HUMAN_HANDOFF`。
- 所有工单与记忆同时绑定 `user_id`，查询时强制使用当前登录用户主键。
- 保存会话摘要、关联订单、问题类型和待补充信息，不保存密码、验证码或支付凭据。
- 使用 `bge-m3` 对当前用户的历史摘要进行向量召回。

## 第二阶段：声明式 Skills

- 在 `skills/` 下建立退款、配送事故、食品安全、支付、取消订单等技能包。
- 每个 `SKILL.md` 描述触发条件、允许工具、执行步骤、风险升级条件和禁止承诺事项。
- `workflow.json` 提供机器可读的输入字段、工具白名单和规则类别。
- Supervisor 只加载与当前任务有关的技能，避免全量提示词污染。

## 第三阶段：Supervisor 与并行专业 Agent

- Supervisor 根据 DeepSeek 规划结果选择 Skill 和子任务。
- 使用 `ThreadPoolExecutor` 并行执行互不依赖的订单、规则、记忆和风险任务。
- 每个专业 Agent 返回结构化结果，不直接生成最终客服话术。
- 汇总节点记录各 Agent 的耗时、命中依据和异常状态。

## 第四阶段：证据审核与行动决策

- 检查订单是否属于当前用户、规则是否满足订单状态、记忆是否属于当前用户。
- 回答必须至少包含规则证据；涉及订单事实时必须具有订单工具结果。
- 食品安全、人身风险、支付安全和证据冲突进入人工处理。
- 满足条件时允许 Case Agent 创建或更新售后工单。

## 第五阶段：MCP 工具服务

- 将订单、工单、记忆和规则检索封装为本地 MCP Server。
- 暴露 `get_my_order`、`list_my_orders_by_date`、`create_after_sales_case`、`append_case_event`、`search_policy`、`recall_memory` 等工具。
- MCP 工具内部继续从会话注入用户主键，不接受模型自行指定授权用户。
- 桌面应用默认内嵌启动 MCP 服务，用户无需额外运行后端。

## 第六阶段：评测与发布

- 增加多意图、跨轮指代、记忆隔离、并行任务、工单状态迁移和 MCP Schema 测试。
- 对比单链路与多 Agent 工作流的正确率、拒答率、平均耗时和工具调用成功率。
- 更新课程设计文档、简历描述和《报错与解决.md》后重新打包 EXE。

## 实施原则

- 不为了展示 Agent 而允许模型执行任意 SQL 或任意工具。
- 多 Agent 只并行执行互不依赖的任务；有依赖关系的任务保持顺序。
- 历史记忆是辅助证据，不能覆盖实时订单状态和正式客服规则。
- MCP 是工具协议层，不替代业务权限校验。
- 未实现的能力不提前写入简历。
