ALTER TABLE user_preferences
ADD COLUMN is_deleted TINYINT(1) NOT NULL DEFAULT 0 AFTER pref_value,
ADD COLUMN deleted_at TIMESTAMP NULL DEFAULT NULL AFTER updated_at;

CREATE TABLE IF NOT EXISTS user_preference_versions (
    version BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id VARCHAR(128) NOT NULL,
    pref_key VARCHAR(128) NOT NULL,
    change_type VARCHAR(32) NOT NULL,
    old_value TEXT NULL,
    new_value TEXT NULL,
    changed_by VARCHAR(128) NOT NULL,
    change_reason VARCHAR(255) NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    KEY idx_pref_versions_user_key_ver (user_id, pref_key, version)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
