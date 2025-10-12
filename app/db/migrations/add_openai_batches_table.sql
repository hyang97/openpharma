-- Migration: Add openai_batches table for tracking OpenAI Batch API jobs
-- Date: 2025-10-12

CREATE TABLE openai_batches (
    openai_batch_id VARCHAR(255) PRIMARY KEY,
    status VARCHAR(50) DEFAULT 'submitted',
    submitted_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP,
    doc_count INTEGER,
    chunk_count INTEGER,
    token_count BIGINT,
    input_file VARCHAR(500),
    output_file VARCHAR(500),
    error_message TEXT
);

ALTER TABLE documents ADD COLUMN openai_batch_id VARCHAR(255) REFERENCES openai_batches(openai_batch_id);

CREATE INDEX idx_openai_batches_status ON openai_batches(status);
CREATE INDEX idx_documents_openai_batch_id ON documents(openai_batch_id);

COMMENT ON TABLE openai_batches IS 'Tracks OpenAI Batch API embedding jobs';
