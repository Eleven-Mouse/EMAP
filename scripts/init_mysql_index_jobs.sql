CREATE TABLE IF NOT EXISTS index_jobs (
    job_id VARCHAR(128) PRIMARY KEY,
    job_type VARCHAR(32) NOT NULL,
    entity_id VARCHAR(128) NOT NULL,
    action_name VARCHAR(32) NOT NULL,
    status VARCHAR(32) NOT NULL,
    payload_json LONGTEXT NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    error_message TEXT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL DEFAULT NULL,
    completed_at TIMESTAMP NULL DEFAULT NULL,
    KEY idx_index_jobs_status_created_at (status, created_at),
    KEY idx_index_jobs_entity (job_type, entity_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
