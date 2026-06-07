CREATE TABLE IF NOT EXISTS knowledge_memories (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    memory_id VARCHAR(128) NOT NULL,
    scope_id VARCHAR(128) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    tags_json LONGTEXT NOT NULL,
    metadata_json LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'active',
    version INT NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL DEFAULT NULL,
    UNIQUE KEY uk_knowledge_memory_id (memory_id),
    KEY idx_knowledge_scope_status (scope_id, status),
    KEY idx_knowledge_updated_at (updated_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_memory_versions (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    memory_id VARCHAR(128) NOT NULL,
    version INT NOT NULL,
    scope_id VARCHAR(128) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content LONGTEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    tags_json LONGTEXT NOT NULL,
    metadata_json LONGTEXT NOT NULL,
    status VARCHAR(32) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    change_note VARCHAR(255) NOT NULL DEFAULT '',
    snapshot_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY uk_knowledge_memory_version (memory_id, version),
    KEY idx_knowledge_memory_versions_memory_id (memory_id)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS knowledge_memory_events (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    memory_id VARCHAR(128) NOT NULL,
    event_type VARCHAR(32) NOT NULL,
    actor_id VARCHAR(128) NOT NULL,
    detail_json LONGTEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_knowledge_memory_events_memory_id (memory_id),
    KEY idx_knowledge_memory_events_created_at (created_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
