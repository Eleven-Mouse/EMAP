CREATE TABLE IF NOT EXISTS documents (
    document_id VARCHAR(128) PRIMARY KEY,
    source VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id VARCHAR(191) PRIMARY KEY,
    document_id VARCHAR(128) NOT NULL,
    content LONGTEXT NOT NULL,
    source VARCHAR(255) NOT NULL,
    chunk_order INT NOT NULL,
    metadata_json LONGTEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_chunks_doc (document_id),
    CONSTRAINT fk_chunks_documents
        FOREIGN KEY (document_id) REFERENCES documents(document_id)
        ON DELETE CASCADE
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
