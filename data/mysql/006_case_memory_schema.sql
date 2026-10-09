USE kangaroo_agent;

CREATE TABLE IF NOT EXISTS after_sales_case (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_code VARCHAR(40) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    order_code VARCHAR(32) NOT NULL,
    issue_type VARCHAR(64) NOT NULL,
    case_status VARCHAR(32) NOT NULL,
    summary VARCHAR(500) NOT NULL,
    required_evidence VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT fk_case_user FOREIGN KEY (user_id) REFERENCES customer_user(id),
    CONSTRAINT fk_case_order FOREIGN KEY (order_code) REFERENCES customer_order(order_code),
    INDEX idx_case_user_order (user_id, order_code),
    INDEX idx_case_user_status (user_id, case_status)
);

CREATE TABLE IF NOT EXISTS case_event (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    case_id BIGINT NOT NULL,
    event_type VARCHAR(64) NOT NULL,
    event_content VARCHAR(1000) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_event_case FOREIGN KEY (case_id) REFERENCES after_sales_case(id),
    INDEX idx_event_case_time (case_id, created_at)
);

CREATE TABLE IF NOT EXISTS conversation_session (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_code VARCHAR(40) NOT NULL UNIQUE,
    user_id BIGINT NOT NULL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ended_at DATETIME NULL,
    CONSTRAINT fk_session_user FOREIGN KEY (user_id) REFERENCES customer_user(id),
    INDEX idx_session_user_time (user_id, started_at)
);

CREATE TABLE IF NOT EXISTS conversation_memory (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    session_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    order_code VARCHAR(32) NULL,
    issue_type VARCHAR(64) NULL,
    summary VARCHAR(1000) NOT NULL,
    pending_information VARCHAR(500) NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_memory_session FOREIGN KEY (session_id) REFERENCES conversation_session(id),
    CONSTRAINT fk_memory_user FOREIGN KEY (user_id) REFERENCES customer_user(id),
    INDEX idx_memory_user_time (user_id, created_at),
    INDEX idx_memory_user_order (user_id, order_code)
);
