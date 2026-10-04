USE kangaroo_agent;

ALTER TABLE customer_user
ADD COLUMN password_hash VARCHAR(255) NULL AFTER display_name;

-- 已有测试用户保持 NULL。首次注册相同 user_code 时，程序允许其设置密码并保留原有订单关系。
