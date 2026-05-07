BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS btree_gist;

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_role') THEN
        CREATE TYPE user_role AS ENUM ('employee', 'manager', 'hr', 'admin');
    ELSE
        -- Ensure 'manager' exists in existing enum
        IF NOT EXISTS (
            SELECT 1 FROM pg_enum
            WHERE enumtypid = (SELECT oid FROM pg_type WHERE typname = 'user_role')
            AND enumlabel = 'manager'
        ) THEN
            ALTER TYPE user_role ADD VALUE 'manager';
        END IF;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'user_status') THEN
        CREATE TYPE user_status AS ENUM ('active', 'inactive');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'conversation_status') THEN
        CREATE TYPE conversation_status AS ENUM ('active', 'closed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'message_sender') THEN
        CREATE TYPE message_sender AS ENUM ('user', 'bot', 'hr_agent', 'system');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sentiment_label') THEN
        CREATE TYPE sentiment_label AS ENUM ('positive', 'neutral', 'negative');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'sentiment_source') THEN
        CREATE TYPE sentiment_source AS ENUM ('chat', 'survey', 'feedback');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_status') THEN
        CREATE TYPE ticket_status AS ENUM ('open', 'in_progress', 'resolved', 'escalated', 'closed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'ticket_priority') THEN
        CREATE TYPE ticket_priority AS ENUM ('low', 'medium', 'high', 'critical');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'survey_type') THEN
        CREATE TYPE survey_type AS ENUM ('pulse', 'onboarding', 'probation', 'exit');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'survey_question_type') THEN
        CREATE TYPE survey_question_type AS ENUM ('text', 'rating', 'mcq');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'meeting_participant_status') THEN
        CREATE TYPE meeting_participant_status AS ENUM ('invited', 'accepted', 'declined', 'tentative');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'email_status') THEN
        CREATE TYPE email_status AS ENUM ('queued', 'sent', 'failed');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attrition_level') THEN
        CREATE TYPE attrition_level AS ENUM ('low', 'medium', 'high');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'attachment_entity_type') THEN
        CREATE TYPE attachment_entity_type AS ENUM ('ticket', 'leave_request');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'celebration_type') THEN
        CREATE TYPE celebration_type AS ENUM ('work_anniversary', 'birthday', 'milestone');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'hr_action_status') THEN
        CREATE TYPE hr_action_status AS ENUM ('pending', 'completed', 'cancelled');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'leave_type') THEN
        CREATE TYPE leave_type AS ENUM ('paid', 'sick', 'work_from_home', 'unpaid');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'leave_status') THEN
        CREATE TYPE leave_status AS ENUM ('pending', 'approved', 'rejected');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'mood_emoji') THEN
        CREATE TYPE mood_emoji AS ENUM ('happy', 'neutral', 'sad', 'upset');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'personal_fact_type') THEN
        CREATE TYPE personal_fact_type AS ENUM ('birthday', 'work_anniversary', 'hobby', 'family_note', 'custom');
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'wellness_tip_type') THEN
        CREATE TYPE wellness_tip_type AS ENUM ('stretch', 'hydration', 'eye_break');
    END IF;
END $$;

CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TABLE departments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id VARCHAR(50) UNIQUE,
    name VARCHAR(100) NOT NULL,
    email CITEXT NOT NULL UNIQUE,
    role user_role NOT NULL DEFAULT 'employee',
    department_id UUID REFERENCES departments(id) ON DELETE SET NULL,
    designation VARCHAR(100),
    manager_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status user_status NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE calendar_integrations (
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

CREATE TABLE integration_providers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider_key VARCHAR(100) NOT NULL UNIQUE,
    provider_type VARCHAR(50) NOT NULL,
    display_name VARCHAR(150) NOT NULL,
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status conversation_status NOT NULL DEFAULT 'active',
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ended_at TIMESTAMPTZ,
    active_flow VARCHAR(100),
    last_intent VARCHAR(100),
    flow_data TEXT,
    state JSONB,
    last_question VARCHAR(255),
    completed BOOLEAN NOT NULL DEFAULT FALSE,
    CHECK (ended_at IS NULL OR ended_at >= started_at)
);

CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    sender message_sender NOT NULL,
    message_text TEXT NOT NULL,
    intent VARCHAR(100),
    sentiment sentiment_label,
    confidence REAL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (confidence IS NULL OR (confidence >= 0 AND confidence <= 1))
);

CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    file_path TEXT NOT NULL,
    uploaded_by UUID REFERENCES users(id) ON DELETE SET NULL,
    checksum_sha256 CHAR(64),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INT NOT NULL,
    content TEXT NOT NULL,
    embedding_id VARCHAR(255) NOT NULL,
    embedding_provider_id UUID NOT NULL REFERENCES integration_providers(id) ON DELETE RESTRICT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (document_id, chunk_index),
    UNIQUE (embedding_provider_id, embedding_id)
);

CREATE TABLE tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    query TEXT NOT NULL,
    category VARCHAR(100) NOT NULL,
    status ticket_status NOT NULL DEFAULT 'open',
    priority ticket_priority NOT NULL DEFAULT 'medium',
    assigned_to UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,
    hash VARCHAR(64),
    sentiment_score INTEGER,
    CHECK (resolved_at IS NULL OR resolved_at >= created_at),
    CHECK (sentiment_score IS NULL OR (sentiment_score >= -100 AND sentiment_score <= 100)),
    CONSTRAINT uq_ticket_user_hash UNIQUE (user_id, hash)
);

CREATE TABLE ticket_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id UUID NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    sender_id UUID REFERENCES users(id) ON DELETE SET NULL,
    message_text TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sentiments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source sentiment_source NOT NULL,
    sentiment sentiment_label NOT NULL,
    score REAL NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (score >= -1 AND score <= 1)
);

CREATE TABLE attrition_risk (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    risk_score REAL NOT NULL,
    risk_level attrition_level NOT NULL DEFAULT 'low',
    reason JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (risk_score >= 0 AND risk_score <= 1)
);

CREATE TABLE surveys (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    type survey_type NOT NULL,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    start_at TIMESTAMPTZ,
    end_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_at IS NULL OR start_at IS NULL OR end_at >= start_at)
);

CREATE TABLE survey_questions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    question_type survey_question_type NOT NULL,
    position INT NOT NULL,
    is_required BOOLEAN NOT NULL DEFAULT TRUE,
    options JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (survey_id, position)
);

CREATE TABLE survey_responses (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    survey_id UUID NOT NULL REFERENCES surveys(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    anonymous_token UUID,
    submitted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        (user_id IS NOT NULL AND anonymous_token IS NULL)
        OR (user_id IS NULL AND anonymous_token IS NOT NULL)
    )
);

CREATE UNIQUE INDEX uq_survey_response_user
ON survey_responses (survey_id, user_id)
WHERE user_id IS NOT NULL;

CREATE UNIQUE INDEX uq_survey_response_anonymous
ON survey_responses (survey_id, anonymous_token)
WHERE anonymous_token IS NOT NULL;

CREATE TABLE survey_answers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    response_id UUID NOT NULL REFERENCES survey_responses(id) ON DELETE CASCADE,
    question_id UUID NOT NULL REFERENCES survey_questions(id) ON DELETE CASCADE,
    answer_text TEXT,
    answer_numeric NUMERIC(10,2),
    answer_option JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (
        answer_text IS NOT NULL OR answer_numeric IS NOT NULL OR answer_option IS NOT NULL
    ),
    UNIQUE (response_id, question_id)
);

CREATE TABLE anonymous_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    category VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    sentiment sentiment_label,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE meetings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(255) NOT NULL,
    organizer_id UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    provider_id UUID REFERENCES integration_providers(id) ON DELETE SET NULL,
    external_event_id VARCHAR(255),
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    location VARCHAR(255),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_time > start_time)
);

CREATE TABLE meeting_participants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    meeting_id UUID NOT NULL REFERENCES meetings(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    status meeting_participant_status NOT NULL DEFAULT 'invited',
    responded_at TIMESTAMPTZ,
    UNIQUE (meeting_id, user_id)
);

CREATE TABLE rooms (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    capacity INT NOT NULL CHECK (capacity > 0),
    location VARCHAR(255) NOT NULL,
    facilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE room_bookings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    room_id UUID NOT NULL REFERENCES rooms(id) ON DELETE RESTRICT,
    booked_by UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    meeting_id UUID REFERENCES meetings(id) ON DELETE SET NULL,
    start_time TIMESTAMPTZ NOT NULL,
    end_time TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (end_time > start_time),
    EXCLUDE USING gist (
        room_id WITH =,
        tstzrange(start_time, end_time, '[)') WITH &&
    )
);

CREATE TABLE email_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    subject VARCHAR(255) NOT NULL,
    body TEXT NOT NULL,
    status email_status NOT NULL DEFAULT 'queued',
    provider_id UUID REFERENCES integration_providers(id) ON DELETE SET NULL,
    provider_message_id VARCHAR(255),
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE activity_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(255) NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TRIGGER trg_departments_updated_at
BEFORE UPDATE ON departments
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_users_updated_at
BEFORE UPDATE ON users
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_calendar_integrations_updated_at
BEFORE UPDATE ON calendar_integrations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_integration_providers_updated_at
BEFORE UPDATE ON integration_providers
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_documents_updated_at
BEFORE UPDATE ON documents
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_tickets_updated_at
BEFORE UPDATE ON tickets
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_surveys_updated_at
BEFORE UPDATE ON surveys
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_meetings_updated_at
BEFORE UPDATE ON meetings
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_rooms_updated_at
BEFORE UPDATE ON rooms
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE INDEX idx_users_department ON users(department_id);
CREATE INDEX idx_users_manager ON users(manager_id);
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_calendar_integrations_user_provider ON calendar_integrations(user_id, provider);
CREATE INDEX idx_calendar_integrations_provider_connected ON calendar_integrations(provider, connected_at DESC);

CREATE INDEX idx_conversations_user_started_at ON conversations(user_id, started_at DESC);
CREATE INDEX idx_conversations_active_flow ON conversations(active_flow);
CREATE INDEX idx_conversations_last_intent ON conversations(last_intent);
CREATE INDEX idx_conversations_completed ON conversations(completed);
CREATE INDEX idx_messages_conversation_created_at ON messages(conversation_id, created_at);
CREATE INDEX idx_messages_intent ON messages(intent);

CREATE INDEX idx_documents_active_created_at ON documents(is_active, created_at DESC);
CREATE INDEX idx_document_chunks_document ON document_chunks(document_id);
CREATE INDEX idx_document_chunks_provider ON document_chunks(embedding_provider_id);

CREATE INDEX idx_tickets_status_priority ON tickets(status, priority);
CREATE INDEX idx_tickets_user_created_at ON tickets(user_id, created_at DESC);
CREATE INDEX idx_tickets_hash ON tickets(hash);
CREATE INDEX idx_ticket_messages_ticket_created_at ON ticket_messages(ticket_id, created_at);

CREATE INDEX idx_sentiments_user_created_at ON sentiments(user_id, created_at DESC);
CREATE INDEX idx_sentiments_source_created_at ON sentiments(source, created_at DESC);
CREATE INDEX idx_attrition_risk_level ON attrition_risk(risk_level, risk_score DESC);

CREATE INDEX idx_survey_questions_survey ON survey_questions(survey_id);
CREATE INDEX idx_survey_responses_survey_submitted_at ON survey_responses(survey_id, submitted_at DESC);
CREATE INDEX idx_survey_answers_response ON survey_answers(response_id);

CREATE INDEX idx_anonymous_feedback_category_created_at ON anonymous_feedback(category, created_at DESC);

CREATE INDEX idx_meetings_organizer_start_time ON meetings(organizer_id, start_time);
CREATE INDEX idx_meetings_provider ON meetings(provider_id);
CREATE INDEX idx_meeting_participants_user ON meeting_participants(user_id);
CREATE INDEX idx_room_bookings_room_start_end ON room_bookings(room_id, start_time, end_time);

CREATE INDEX idx_email_logs_user_created_at ON email_logs(user_id, created_at DESC);
CREATE INDEX idx_email_logs_provider ON email_logs(provider_id);

CREATE INDEX idx_activity_logs_user_created_at ON activity_logs(user_id, created_at DESC);
CREATE INDEX idx_activity_logs_metadata_gin ON activity_logs USING GIN (metadata);

CREATE TABLE user_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    name VARCHAR(100),
    department VARCHAR(100),
    preferences JSONB,
    last_summary TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE conversation_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    summary TEXT NOT NULL,
    tags JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE chat_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES conversations(id) ON DELETE SET NULL,
    rating INT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    intent VARCHAR(100),
    sentiment VARCHAR(32),
    source VARCHAR(32) NOT NULL DEFAULT 'chat',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_user_profiles_user_id ON user_profiles(user_id);
CREATE INDEX idx_conversation_memory_user_created ON conversation_memory(user_id, created_at DESC);
CREATE INDEX idx_chat_feedback_user_created ON chat_feedback(user_id, created_at DESC);
CREATE INDEX idx_chat_feedback_created ON chat_feedback(created_at DESC);
CREATE INDEX idx_chat_feedback_rating ON chat_feedback(rating);

-- Onboarding Buddies
CREATE TABLE onboarding_buddies (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    buddy_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    active_until TIMESTAMPTZ,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    notes TEXT,
    UNIQUE (user_id, is_active)
);

CREATE INDEX idx_onboarding_buddies_user ON onboarding_buddies(user_id);
CREATE INDEX idx_onboarding_buddies_buddy ON onboarding_buddies(buddy_id);
CREATE INDEX idx_onboarding_buddies_active ON onboarding_buddies(is_active, active_until);

-- Analytics tables for Phase 1: Advanced Analytics & AI
CREATE TABLE IF NOT EXISTS mental_health_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    score INTEGER NOT NULL CHECK (score >= 0 AND score <= 100),
    factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    trend VARCHAR(20) NOT NULL DEFAULT 'stable',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, created_at_date)
);

CREATE OR REPLACE FUNCTION created_at_date()
RETURNS TRIGGER AS $$
BEGIN
    NEW.created_at_date = NEW.created_at::date;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

ALTER TABLE mental_health_scores ADD COLUMN IF NOT EXISTS created_at_date DATE GENERATED ALWAYS AS (created_at::date) STORED;

CREATE TABLE IF NOT EXISTS burnout_predictions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    risk_score REAL NOT NULL CHECK (risk_score >= 0 AND risk_score <= 1),
    risk_level VARCHAR(20) NOT NULL DEFAULT 'low',
    factors JSONB NOT NULL DEFAULT '{}'::jsonb,
    confidence REAL,
    predicted_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    window_start TIMESTAMPTZ NOT NULL,
    window_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_burnout_predictions_user_date ON burnout_predictions(user_id, predicted_at DESC);

CREATE TABLE IF NOT EXISTS sentiment_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    source VARCHAR(50) NOT NULL,
    sentiment VARCHAR(20) NOT NULL,
    score REAL NOT NULL,
    context JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_sentiment_history_user_date ON sentiment_history(user_id, created_at DESC);

-- Executive dashboard aggregated data
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    snapshot_date DATE NOT NULL UNIQUE,
    total_users INTEGER NOT NULL DEFAULT 0,
    active_users INTEGER NOT NULL DEFAULT 0,
    engagement_score REAL,
    enps REAL,
    avg_sentiment REAL,
    open_tickets INTEGER NOT NULL DEFAULT 0,
    resolved_tickets INTEGER NOT NULL DEFAULT 0,
    avg_response_time_minutes REAL,
    burnout_high_risk_count INTEGER NOT NULL DEFAULT 0,
    attrition_high_risk_count INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Insights generated by the insights engine
CREATE TABLE IF NOT EXISTS insights (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    insight_type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT NOT NULL,
    severity VARCHAR(20) NOT NULL DEFAULT 'info',
    affected_entity_type VARCHAR(50),
    affected_entity_id UUID,
    metrics JSONB,
    recommendations JSONB,
    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_insights_unresolved ON insights(created_at DESC) WHERE is_resolved = FALSE;

-- HR response suggestions for AI enhancement
CREATE TABLE IF NOT EXISTS response_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    query_context TEXT NOT NULL,
    suggested_response TEXT NOT NULL,
    quality_score REAL,
    usage_count INTEGER NOT NULL DEFAULT 0,
    is_approved BOOLEAN NOT NULL DEFAULT FALSE,
    created_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Proactive signal and automation tables
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

CREATE UNIQUE INDEX uq_automation_actions_rule_idempotency
ON automation_actions (rule_name, idempotency_key)
WHERE idempotency_key IS NOT NULL;

CREATE INDEX idx_activity_events_user_event_at ON activity_events (user_id, event_at DESC);
CREATE INDEX idx_activity_events_type_event_at ON activity_events (event_type, event_at DESC);
CREATE INDEX idx_activity_events_metadata_gin ON activity_events USING GIN (metadata);

CREATE INDEX idx_reminder_schedules_user_status_next ON reminder_schedules (user_id, status, next_trigger_at);
CREATE INDEX idx_reminder_schedules_status_next ON reminder_schedules (status, next_trigger_at);

CREATE INDEX idx_wellbeing_signals_user_computed ON wellbeing_signals (user_id, computed_at DESC);
CREATE INDEX idx_wellbeing_signals_triage ON wellbeing_signals (triage_level, computed_at DESC);
CREATE INDEX idx_wellbeing_signals_followup ON wellbeing_signals (requires_hr_followup, computed_at DESC);

CREATE INDEX idx_risk_snapshots_user_period ON risk_snapshots (user_id, period_end DESC);
CREATE INDEX idx_risk_snapshots_attrition ON risk_snapshots (attrition_risk DESC, confidence DESC);

CREATE INDEX idx_automation_actions_status_schedule ON automation_actions (status, scheduled_for);
CREATE INDEX idx_automation_actions_user_created ON automation_actions (user_id, created_at DESC);

CREATE TABLE appreciation_notes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    from_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    to_user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    message TEXT NOT NULL,
    is_anonymous BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE attachments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    file_name VARCHAR(255) NOT NULL,
    file_type VARCHAR(100) NOT NULL,
    file_size INTEGER NOT NULL,
    file_path VARCHAR(500) NOT NULL,
    entity_type attachment_entity_type NOT NULL,
    entity_id UUID NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE celebrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    celebration_type celebration_type NOT NULL,
    celebration_date DATE NOT NULL,
    years_count INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE hr_actions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    employee_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    action_type VARCHAR(50) NOT NULL,
    status hr_action_status NOT NULL DEFAULT 'pending',
    scheduled_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE hr_alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    body TEXT,
    severity VARCHAR(32) NOT NULL DEFAULT 'medium',
    alert_type VARCHAR(64),
    source VARCHAR(64) NOT NULL DEFAULT 'proactive_wellbeing',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    acknowledged BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE leave_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    leave_type leave_type NOT NULL,
    reason TEXT,
    status leave_status NOT NULL DEFAULT 'pending',
    manager_id UUID REFERENCES users(id) ON DELETE SET NULL,
    reviewed_at TIMESTAMPTZ,
    review_comment TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE meeting_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    meeting_title VARCHAR(255),
    meeting_id VARCHAR(100),
    duration_minutes INTEGER,
    meeting_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE mood_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mood_emoji mood_emoji NOT NULL,
    mood_score INTEGER NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE onboarding_checklist (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    task_name VARCHAR(200) NOT NULL,
    task_description VARCHAR(1000),
    is_completed BOOLEAN NOT NULL DEFAULT FALSE,
    completed_at TIMESTAMPTZ,
    due_date TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE personal_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    fact_type personal_fact_type NOT NULL,
    fact_value TEXT NOT NULL,
    source_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE slack_integrations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    slack_user_id VARCHAR(32),
    slack_team_id VARCHAR(32),
    access_token TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_mood BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_appreciation BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_tickets BOOLEAN NOT NULL DEFAULT TRUE,
    notify_on_calendar BOOLEAN NOT NULL DEFAULT FALSE,
    notify_on_leave BOOLEAN NOT NULL DEFAULT TRUE,
    dm_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    channel_notifications BOOLEAN NOT NULL DEFAULT FALSE,
    notification_channel VARCHAR(64),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_slack_integrations_user UNIQUE (user_id)
);

CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name VARCHAR(128) NOT NULL,
    url TEXT NOT NULL,
    secret VARCHAR(128),
    event_type VARCHAR(64) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    status VARCHAR(16) NOT NULL DEFAULT 'active',
    max_retries INTEGER NOT NULL DEFAULT 3,
    retry_delay_seconds INTEGER NOT NULL DEFAULT 60,
    method VARCHAR(8) NOT NULL DEFAULT 'POST',
    headers TEXT,
    total_requests INTEGER NOT NULL DEFAULT 0,
    successful_requests INTEGER NOT NULL DEFAULT 0,
    failed_requests INTEGER NOT NULL DEFAULT 0,
    last_triggered_at TIMESTAMPTZ,
    last_successful_at TIMESTAMPTZ,
    last_failed_at TIMESTAMPTZ,
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_webhooks_user_name UNIQUE (user_id, name)
);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID NOT NULL REFERENCES webhooks(id) ON DELETE CASCADE,
    event_type VARCHAR(64) NOT NULL,
    payload TEXT NOT NULL,
    method VARCHAR(8) NOT NULL DEFAULT 'POST',
    status_code INTEGER,
    response_body TEXT,
    attempt INTEGER NOT NULL DEFAULT 0,
    is_successful BOOLEAN NOT NULL DEFAULT FALSE,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE wellness_tips (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tip_type wellness_tip_type NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    emoji VARCHAR(10) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_appreciation_notes_from_user_id ON appreciation_notes(from_user_id);
CREATE INDEX ix_appreciation_notes_to_user_id ON appreciation_notes(to_user_id);
CREATE INDEX ix_appreciation_notes_is_anonymous ON appreciation_notes(is_anonymous);
CREATE INDEX ix_appreciation_notes_created_at ON appreciation_notes(created_at);

CREATE INDEX ix_attachments_user_id ON attachments(user_id);
CREATE INDEX ix_attachments_entity_type ON attachments(entity_type);
CREATE INDEX ix_attachments_entity_id ON attachments(entity_id);
CREATE INDEX ix_attachments_created_at ON attachments(created_at);

CREATE INDEX ix_celebrations_user_id ON celebrations(user_id);
CREATE INDEX ix_celebrations_celebration_type ON celebrations(celebration_type);
CREATE INDEX ix_celebrations_celebration_date ON celebrations(celebration_date);
CREATE INDEX ix_celebrations_created_at ON celebrations(created_at);

CREATE INDEX ix_hr_actions_employee_id ON hr_actions(employee_id);
CREATE INDEX ix_hr_actions_status ON hr_actions(status);
CREATE INDEX ix_hr_actions_scheduled_at ON hr_actions(scheduled_at);
CREATE INDEX ix_hr_actions_created_at ON hr_actions(created_at);

CREATE INDEX ix_hr_alerts_acknowledged ON hr_alerts(acknowledged);
CREATE INDEX ix_hr_alerts_created_at ON hr_alerts(created_at);

CREATE INDEX ix_leave_requests_user_id ON leave_requests(user_id);
CREATE INDEX ix_leave_requests_start_date ON leave_requests(start_date);
CREATE INDEX ix_leave_requests_leave_type ON leave_requests(leave_type);
CREATE INDEX ix_leave_requests_status ON leave_requests(status);
CREATE INDEX ix_leave_requests_manager_id ON leave_requests(manager_id);
CREATE INDEX ix_leave_requests_created_at ON leave_requests(created_at);

CREATE INDEX ix_meeting_events_user_id ON meeting_events(user_id);
CREATE INDEX ix_meeting_events_meeting_id ON meeting_events(meeting_id);
CREATE INDEX ix_meeting_events_meeting_at ON meeting_events(meeting_at);
CREATE INDEX ix_meeting_events_created_at ON meeting_events(created_at);

CREATE INDEX ix_mood_entries_user_id ON mood_entries(user_id);
CREATE INDEX ix_mood_entries_mood_emoji ON mood_entries(mood_emoji);
CREATE INDEX ix_mood_entries_created_at ON mood_entries(created_at);

CREATE INDEX ix_onboarding_checklist_user_id ON onboarding_checklist(user_id);
CREATE INDEX ix_onboarding_checklist_is_completed ON onboarding_checklist(is_completed);

CREATE INDEX ix_personal_facts_user_id ON personal_facts(user_id);
CREATE INDEX ix_personal_facts_fact_type ON personal_facts(fact_type);
CREATE INDEX ix_personal_facts_source_message_id ON personal_facts(source_message_id);
CREATE INDEX ix_personal_facts_created_at ON personal_facts(created_at);

CREATE INDEX ix_slack_integrations_user_id ON slack_integrations(user_id);

CREATE INDEX ix_webhooks_user_id ON webhooks(user_id);
CREATE INDEX ix_webhooks_event_type ON webhooks(event_type);
CREATE INDEX ix_webhooks_user_event ON webhooks(user_id, event_type);

CREATE INDEX ix_webhook_deliveries_webhook_id ON webhook_deliveries(webhook_id);
CREATE INDEX ix_webhook_deliveries_webhook_created ON webhook_deliveries(webhook_id, created_at);

CREATE INDEX ix_wellness_tips_tip_type ON wellness_tips(tip_type);
CREATE INDEX ix_wellness_tips_is_active ON wellness_tips(is_active);
CREATE INDEX ix_wellness_tips_created_at ON wellness_tips(created_at);

CREATE TRIGGER trg_hr_actions_updated_at
BEFORE UPDATE ON hr_actions
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_personal_facts_updated_at
BEFORE UPDATE ON personal_facts
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_slack_integrations_updated_at
BEFORE UPDATE ON slack_integrations
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE TRIGGER trg_webhooks_updated_at
BEFORE UPDATE ON webhooks
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

COMMIT;
