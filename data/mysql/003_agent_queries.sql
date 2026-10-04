USE kangaroo_agent;

-- Agent 根据当前登录用户主键查询订单，只返回订单号和订单状态。
SELECT o.order_code, o.order_status
FROM customer_order o
WHERE o.user_id = ?
ORDER BY o.created_at DESC;

-- Agent 根据当前用户主键和订单号查询单个订单。
SELECT o.order_code, o.order_status
FROM customer_order o
WHERE o.user_id = ? AND o.order_code = ?;

-- 禁止只按订单号查询，避免越权获取其他用户的订单状态。
