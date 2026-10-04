# 美团袋鼠可信客服桌宠 Agent

这是一个面向 Windows 桌面的客服桌宠项目。桌宠使用美团袋鼠作为交互形象，Agent 面向外卖配送、退款售后等客服场景，通过客服知识库生成带证据来源的回答。

## 当前状态

项目已实现登录注册、本人订单工具调用、LangGraph Agent、可信规则检索、DeepSeek 在线生成、离线降级、桌宠交互和 EXE 打包。

## 设计原则

- 使用 DeepSeek API 进行在线回答，API 不可用时切换到离线检索/抽取式回答；
- 普通 RAG 和可信 RAG 保留为对照实验；
- 知识库证据不足时拒答、澄清或转人工，不强行生成；
- 桌宠界面展示回答、来源、可信状态和必要的人工升级入口；
- 最终支持 Windows 一键启动和 PyInstaller EXE 打包；
- 不在仓库中保存真实 API Key。

## 计划技术栈

- Python 3.12：Agent、RAG、评测和桌面端；
- LangGraph：用于组织问题分类、检索、证据校验、回答/拒答/转人工状态流；
- PySide6：Windows 桌面窗口、系统托盘和桌宠交互；
- `bge-m3`：从 `E:\AA_embedding` 完全离线加载，执行真实语义向量检索；
- DeepSeek API：在线生成；
- PyInstaller：打包 EXE；
- Node.js：暂不作为核心运行时，若后续需要可用于前端资源构建。

## 开发前准备

1. 复制 `.env.example` 为 `.env`。
2. 填写 `DEEPSEEK_API_KEY`，不要提交 `.env`。
3. 确保 `E:\AA_embedding` 中已有 `BAAI/bge-m3` 模型缓存。
4. 客服规则位于 `data/knowledge/customer_rules.jsonl`，修改后会自动重建规则向量缓存。

## 当前启动方式

- 双击 `run_desktop.bat` 启动袋鼠桌宠；
- 桌宠启动时会自动启动客户可读的规则来源服务；`run_sources.bat` 仅用于单独调试来源页面；
- 项目依赖安装在 D 盘项目目录的 `.venv`，不使用全局 Python 环境。

当前登录用户由 `.env` 中的 `CURRENT_USER_ID` 指定，未填写时默认为测试用户主键 `1`。

新版桌宠启动后先显示登录/注册窗口，实际 Agent 会话使用登录用户在 MySQL 中的主键；`CURRENT_USER_ID` 仅保留给命令行调试脚本。

检索不是关键词包含匹配：规则被编码为 1024 维向量，用户问题通过余弦相似度排序，并使用最低分数与 Top1/Top2 区分度双门槛拒绝不可靠召回。界面会展示 `BAAI/bge-m3`、命中文档和相似度。

用户未提供订单号时，Agent 会先查询当前登录用户的当天订单：一笔订单自动选中，多笔订单显示可点击选择按钮，没有当天订单才请求用户提供订单号。可执行 `data/mysql/005_today_order_demo.sql` 为 `U10001` 创建两笔当天演示订单。

## Agent 工作流

每轮请求首先由 DeepSeek 规划器输出受约束 JSON（意图、风险、订单号、订单日期、是否需要订单）。程序校验字段后才允许调用白名单工具；模型不能生成或执行 SQL，也不能指定用户主键。订单工具始终使用登录会话中的用户 ID 查询 MySQL。之后使用 `bge-m3` 从 JSONL 规则库召回证据并执行状态、阈值和来源校验，最后把用户问题、订单工具结果和规则证据交给 DeepSeek 生成回答。规划或回答 API 不可用时分别切换到离线规划器和离线规则模板，并在界面明确标识。

打包后的程序位于 `dist/KangarooCustomerAgent/KangarooCustomerAgent.exe`。首次使用已有测试用户时，请在注册界面为该用户编号设置密码；注册不会新增订单。

## 目录

```text
A_Kangaroo_Trustworthy_Agent/
├── backend/       Agent、检索、证据和评测
├── data/          知识库、评测集和数据结构
├── desktop/       袋鼠桌宠界面与素材
├── docs/          设计、运行和问题记录
├── experiments/   实验配置、结果和图表
├── scripts/       建库、评测和打包脚本
└── tests/         自动化测试
```
