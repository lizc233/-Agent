USE kangaroo_agent;

ALTER TABLE conversation_session
    ADD COLUMN pending_question VARCHAR(1000) NULL;
