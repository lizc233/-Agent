USE kangaroo_agent;

ALTER TABLE conversation_session
    ADD COLUMN current_order_code VARCHAR(32) NULL,
    ADD COLUMN current_order_status VARCHAR(64) NULL,
    ADD COLUMN current_issue_type VARCHAR(64) NULL,
    ADD COLUMN waiting_for VARCHAR(64) NULL,
    ADD COLUMN last_confirmed_fact VARCHAR(500) NULL,
    ADD COLUMN updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP;
