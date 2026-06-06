CREATE TABLE IF NOT EXISTS session_summaries (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(128) NOT NULL,
    session_id VARCHAR(128) NOT NULL,
    summary_text LONGTEXT NOT NULL,
    last_message_count INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uk_session_summary_checkpoint (session_id, last_message_count),
    KEY idx_session_summary_user (user_id, updated_at),
    KEY idx_session_summary_session (session_id, updated_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
