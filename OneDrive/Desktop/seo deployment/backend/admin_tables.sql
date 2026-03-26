-- Admin Dashboard Tables — Phase 2
-- Run against ai1stseo database on RDS

-- Platform-wide usage metrics (aggregated daily by EventBridge Lambda)
CREATE TABLE IF NOT EXISTS admin_metrics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    metric_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_users INTEGER DEFAULT 0,
    new_signups INTEGER DEFAULT 0,
    active_users_24h INTEGER DEFAULT 0,
    active_users_7d INTEGER DEFAULT 0,
    total_scans INTEGER DEFAULT 0,
    total_deep_scans INTEGER DEFAULT 0,
    total_content_briefs INTEGER DEFAULT 0,
    total_geo_probes INTEGER DEFAULT 0,
    avg_seo_score NUMERIC(5,2),
    bedrock_calls INTEGER DEFAULT 0,
    ollama_fallback_calls INTEGER DEFAULT 0,
    scan_errors_count INTEGER DEFAULT 0,
    estimated_ai_cost_usd NUMERIC(8,4) DEFAULT 0,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_admin_metrics_date ON admin_metrics(metric_date);

-- AI usage tracking (per-call cost estimation)
CREATE TABLE IF NOT EXISTS ai_usage_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider VARCHAR(50) NOT NULL,
    model VARCHAR(100) NOT NULL,
    input_tokens_est INTEGER DEFAULT 0,
    output_tokens_est INTEGER DEFAULT 0,
    estimated_cost_usd NUMERIC(8,6) DEFAULT 0,
    success BOOLEAN DEFAULT TRUE,
    latency_ms INTEGER,
    triggered_by VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ai_usage_provider ON ai_usage_log(provider);
CREATE INDEX IF NOT EXISTS idx_ai_usage_created ON ai_usage_log(created_at DESC);

-- API request log (lightweight, for usage tracking)
CREATE TABLE IF NOT EXISTS api_request_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    user_id UUID REFERENCES users(id),
    project_id UUID REFERENCES projects(id),
    status_code INTEGER,
    response_time_ms INTEGER,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_api_log_endpoint ON api_request_log(endpoint);
CREATE INDEX IF NOT EXISTS idx_api_log_created ON api_request_log(created_at DESC);
