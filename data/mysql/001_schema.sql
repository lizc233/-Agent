CREATE DATABASE IF NOT EXISTS kangaroo_agent DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE kangaroo_agent;

CREATE TABLE IF NOT EXISTS customer_user (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_code VARCHAR(32) NOT NULL UNIQUE,
    display_name VARCHAR(64) NOT NULL,
    password_hash VARCHAR(255) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS customer_order (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_code VARCHAR(32) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    order_status VARCHAR(32) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_order_user FOREIGN KEY (user_id) REFERENCES customer_user(id),
    INDEX idx_order_user_status (user_id, order_status)
);

CREATE TABLE IF NOT EXISTS agent_audit_log (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    question TEXT NOT NULL,
    action VARCHAR(32) NOT NULL,
    source_rule_id VARCHAR(64) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_audit_user FOREIGN KEY (user_id) REFERENCES customer_user(id)
);
