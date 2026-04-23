BEGIN;

CREATE TABLE IF NOT EXISTS calendar_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    provider VARCHAR(32) NOT NULL,
    access_token TEXT,
    refresh_token TEXT,
    token_type VARCHAR(32) NOT NULL DEFAULT 'Bearer',
    expires_at TIMESTAMPTZ,
    connected_at TIMESTAMPTZ,
    oauth_state_hash VARCHAR(128),
    oauth_state_expires_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_calendar_integrations_user_provider UNIQUE (user_id, provider),
    CONSTRAINT ck_calendar_integrations_provider CHECK (provider IN ('google', 'microsoft'))
);

CREATE INDEX IF NOT EXISTS idx_calendar_integrations_user_provider
ON calendar_integrations (user_id, provider);

CREATE INDEX IF NOT EXISTS idx_calendar_integrations_provider_connected
ON calendar_integrations (provider, connected_at DESC);

COMMIT;
