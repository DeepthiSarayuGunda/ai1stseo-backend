-- Developer API keys for programmatic access
CREATE TABLE IF NOT EXISTS api_keys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    key_hash VARCHAR(64) NOT NULL,
    key_prefix VARCHAR(12) NOT NULL,
    label VARCHAR(255),
    scopes TEXT[] DEFAULT '{read}',
    rate_limit_per_hour INTEGER DEFAULT 100,
    requests_this_hour INTEGER DEFAULT 0,
    hour_window TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    created_by UUID REFERENCES users(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_apikeys_hash ON api_keys(key_hash);
CREATE INDEX IF NOT EXISTS idx_apikeys_prefix ON api_keys(key_prefix);
CREATE INDEX IF NOT EXISTS idx_apikeys_project ON api_keys(project_id);
