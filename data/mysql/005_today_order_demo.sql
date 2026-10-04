USE kangaroo_agent;

-- 可选演示数据：为 U10001 创建两笔当天订单，用于展示 Agent 的订单选择按钮。
-- order_code 包含当天日期；重复执行时不会重复插入。
INSERT INTO customer_order (order_code, user_id, order_status, created_at)
SELECT CONCAT('OD', DATE_FORMAT(CURRENT_DATE(), '%Y%m%d'), 'A01'), id, 'DELIVERING', NOW()
FROM customer_user
WHERE user_code = 'U10001'
  AND NOT EXISTS (
      SELECT 1 FROM customer_order
      WHERE order_code = CONCAT('OD', DATE_FORMAT(CURRENT_DATE(), '%Y%m%d'), 'A01')
  );

INSERT INTO customer_order (order_code, user_id, order_status, created_at)
SELECT CONCAT('OD', DATE_FORMAT(CURRENT_DATE(), '%Y%m%d'), 'A02'), id, 'COMPLETED', NOW()
FROM customer_user
WHERE user_code = 'U10001'
  AND NOT EXISTS (
      SELECT 1 FROM customer_order
      WHERE order_code = CONCAT('OD', DATE_FORMAT(CURRENT_DATE(), '%Y%m%d'), 'A02')
  );
