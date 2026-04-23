BEGIN;

CREATE TABLE IF NOT EXISTS activity_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    event_type VARCHAR(80) NOT NULL,
    event_source VARCHAR(40) NOT NULL DEFAULT 'web',
    activity_state VARCHAR(24),
    event_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (char_length(event_type) > 0)
);

CREATE TABLE IF NOT EXISTS reminder_schedules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    reminder_type VARCHAR(32) NOT NULL,
    title VARCHAR(150) NOT NULL,
    message TEXT NOT NULL,
    schedule_kind VARCHAR(16) NOT NULL DEFAULT 'one_time',
    run_at TIMESTAMPTZ,
    cron_expr VARCHAR(120),
    timezone VARCHAR(64) NOT NULL DEFAULT 'UTC',
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    last_triggered_at TIMESTAMPTZ,
    next_trigger_at TIMESTAMPTZ,
    payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (schedule_kind IN ('one_time', 'daily', 'weekly', 'cron')),
    CHECK (status IN ('active', 'paused', 'cancelled')),
    CHECK (
        (schedule_kind = 'one_time' AND run_at IS NOT NULL)
        OR (schedule_kind <> 'one_time')
    )
);

CREATE TABLE IF NOT EXISTS wellbeing_signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    source VARCHAR(24) NOT NULL DEFAULT 'chat',
    sentiment_label VARCHAR(16) NOT NULL,
    sentiment_score REAL NOT NULL,
    stress_indicator REAL NOT NULL DEFAULT 0,
    burnout_indicator REAL NOT NULL DEFAULT 0,
    triage_level VARCHAR(16) NOT NULL DEFAULT 'none',
    requires_hr_followup BOOLEAN NOT NULL DEFAULT FALSE,
    detected_keywords JSONB NOT NULL DEFAULT '[]'::jsonb,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    CHECK (sentiment_label IN ('positive', 'neutral', 'negative')),
    CHECK (sentiment_score >= -1 AND sentiment_score <= 1),
    CHECK (stress_indicator >= 0 AND stress_indicator <= 1),
    CHECK (burnout_indicator >= 0 AND burnout_indicator <= 1),
    CHECK (triage_level IN ('none', 'watch', 'high'))
);

CREATE TABLE IF NOT EXISTS risk_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    engagement_score REAL,
    mood_score REAL,
    burnout_risk REAL,
    attrition_risk REAL,
    silence_risk REAL,
    confidence REAL,
    risk_reasons JSONB NOT NULL DEFAULT '[]'::jsonb,
    recommendations JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, period_start, period_end),
    CHECK (period_end >= period_start),
    CHECK (engagement_score IS NULL OR (engagement_score >= 0 AND engagement_score <= 100)),
    CHECK (mood_score IS NULL OR (mood_score >= 0 AND mood_score <= 100)),
    CHECK (burnout_risk IS NULL OR (burnout_risk >= 0 AND burnout_risk <= 1)),
    CHECK (attrition_risk IS NULL OR (attrition_risk >= 0 AND attrition_risk <= 1)),
    CHECK (silence_risk IS NULL OR (silence_risk >= 0 AND silence_risk <= 1)),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE IF NOT EXISTS automation_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_name VARCHAR(80) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    target_type VARCHAR(40) NOT NULL,
    action_type VARCHAR(40) NOT NULL,
    trigger_event_id UUID REFERENCES activity_events(id) ON DELETE SET NULL,
    trigger_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    scheduled_for TIMESTAMPTZ,
    executed_at TIMESTAMPTZ,
    failure_reason TEXT,
    idempotency_key VARCHAR(120),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (status IN ('queued', 'sent', 'failed', 'skipped'))
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_automation_actions_rule_idempotency
ON automation_actions (rule_name, idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_activity_events_user_event_at
ON activity_events (user_id, event_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_events_type_event_at
ON activity_events (event_type, event_at DESC);

CREATE INDEX IF NOT EXISTS idx_activity_events_metadata_gin
ON activity_events USING GIN (metadata);

CREATE INDEX IF NOT EXISTS idx_reminder_schedules_user_status_next
ON reminder_schedules (user_id, status, next_trigger_at);

CREATE INDEX IF NOT EXISTS idx_reminder_schedules_status_next
ON reminder_schedules (status, next_trigger_at);

CREATE INDEX IF NOT EXISTS idx_wellbeing_signals_user_computed
ON wellbeing_signals (user_id, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_wellbeing_signals_triage
ON wellbeing_signals (triage_level, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_wellbeing_signals_followup
ON wellbeing_signals (requires_hr_followup, computed_at DESC);

CREATE INDEX IF NOT EXISTS idx_risk_snapshots_user_period
ON risk_snapshots (user_id, period_end DESC);

CREATE INDEX IF NOT EXISTS idx_risk_snapshots_attrition
ON risk_snapshots (attrition_risk DESC, confidence DESC);

CREATE INDEX IF NOT EXISTS idx_automation_actions_status_schedule
ON automation_actions (status, scheduled_for);

CREATE INDEX IF NOT EXISTS idx_automation_actions_user_created
ON automation_actions (user_id, created_at DESC);

COMMIT;
