# 本地业务数据

业务数据已经改为 MySQL 表，不再使用 JSON 保存用户和订单。

请查看 `data/mysql/`：

- `001_schema.sql`：建库、用户表、订单表和审计表；
- `002_seed.sql`：少量测试用户和订单；
- `003_agent_queries.sql`：Agent 专用查询语句。
