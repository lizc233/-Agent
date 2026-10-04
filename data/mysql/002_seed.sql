USE kangaroo_agent;

INSERT INTO customer_user (user_code, display_name) VALUES
('U10001', '测试用户甲'),
('U10002', '测试用户乙'),
('U10003', '测试用户丙');

INSERT INTO customer_order (order_code, user_id, order_status) VALUES
('OD202610010001', (SELECT id FROM customer_user WHERE user_code = 'U10001'), 'DELIVERING'),
('OD202610010002', (SELECT id FROM customer_user WHERE user_code = 'U10001'), 'DELIVERY_TIMEOUT'),
('OD202610010003', (SELECT id FROM customer_user WHERE user_code = 'U10002'), 'WAITING_ACCEPT'),
('OD202610010004', (SELECT id FROM customer_user WHERE user_code = 'U10002'), 'COMPLETED'),
('OD202610010005', (SELECT id FROM customer_user WHERE user_code = 'U10003'), 'PREPARING'),
('OD202610010006', (SELECT id FROM customer_user WHERE user_code = 'U10003'), 'CANCELLED');
