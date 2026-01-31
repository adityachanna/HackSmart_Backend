this is schema of my table in postgres in supabase refer this dont try to change it and strictly follow it CREATE TABLE cities (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    state VARCHAR(100)
);
CREATE TABLE agents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- BASIC INFO
    name VARCHAR(150) NOT NULL,
    employee_id VARCHAR(50) UNIQUE,
    languages TEXT[],

    -- CURRENT METRICS (0–1)
    current_quality_score DECIMAL(5,4) DEFAULT 0.0,
    current_sop_state_compliance_score DECIMAL(5,4) DEFAULT 0.0,
    current_sentiment_stabilization_score DECIMAL(5,4) DEFAULT 0.0,
    current_escalation_rate DECIMAL(5,4) DEFAULT 0.0,

    calls_handled_total INT DEFAULT 0,
    total_emergencies_count INT DEFAULT 0,

    -- DAILY SNAPSHOT
    calls_handled_today INT DEFAULT 0,
    emergencies_today INT DEFAULT 0,

    -- PREVIOUS MONTH SNAPSHOT
    prev_month_quality_score DECIMAL(5,4),
    prev_month_sop_state_compliance_score DECIMAL(5,4),
    prev_month_sentiment_stabilization_score DECIMAL(5,4),
    prev_month_escalation_rate DECIMAL(5,4),
    prev_month_calls_handled INT,
    prev_month_emergencies INT,

    -- LLM INSIGHTS
    latest_month_insight TEXT,
    overall_insight_text TEXT,
    latest_change_summary TEXT,
    daily_agent_insight TEXT,

    -- MEMORY / TRENDS
    insight_history JSONB DEFAULT '[]'::jsonb,
    recent_trend_array JSONB DEFAULT '[]'::jsonb,

    last_updated_at TIMESTAMP DEFAULT NOW()
);
 CREATE TABLE calls (

    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),



    agent_id UUID REFERENCES agents(id) ON DELETE SET NULL,

    city_id INT REFERENCES cities(id) ON DELETE SET NULL,



    customer_phone VARCHAR(20),

    customer_name VARCHAR(100),



    audio_url TEXT NOT NULL,

    duration_seconds INT,



    call_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),



    call_context VARCHAR(30) NOT NULL

        CHECK (call_context IN (

            'NEW_ISSUE',

            'FOLLOW_UP',

            'ONGOING_CASE',

            'REOPENED',

            'INFORMATION_ONLY',

            'CLOSED_ISSUE'

        )),



    primary_issue_category VARCHAR(50),

    agent_manual_note TEXT,



    processing_status VARCHAR(20) DEFAULT 'pending'

        CHECK (processing_status IN (

            'pending',

            'transcribed',

            'analyzed',

            'failed'

        ))

);

CREATE TABLE call_insights (

    call_id UUID PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE,



    transcript TEXT,

    language_spoken VARCHAR(50),



    -- =========================

    -- CORE SCORES (0–1)

    -- =========================

    sop_state_compliance_score DECIMAL(5,4) NOT NULL

        CHECK (sop_state_compliance_score BETWEEN 0 AND 1),



    conversation_control_score DECIMAL(5,4) NOT NULL

        CHECK (conversation_control_score BETWEEN 0 AND 1),



    sentiment_stabilization_score DECIMAL(3,2) NOT NULL

        CHECK (sentiment_stabilization_score IN (0, 0.5, 1)),



    resolution_path_validity_score DECIMAL(3,2) NOT NULL

        CHECK (resolution_path_validity_score IN (0, 0.75, 1)),



    -- =========================

    -- DERIVED CALL QUALITY

    -- =========================

    overall_call_quality_score DECIMAL(5,4) NOT NULL

        CHECK (overall_call_quality_score BETWEEN 0 AND 1),



    -- =========================

    -- ESCALATION SIGNAL

    -- =========================

    escalation_risk BOOLEAN NOT NULL,



    why_flagged TEXT,

    -- Machine-generated reasoning for the flag



    -- =========================

    -- HUMAN INTERVENTION

    -- =========================

    human_remarks TEXT NULL,

    -- Added: For supervisors to leave manual feedback/notes



    -- =========================

    -- LLM INSIGHTS

    -- =========================

    business_insight TEXT,

    coaching_insight TEXT,



    created_at TIMESTAMP DEFAULT NOW(),



    -- =========================

    -- INVARIANTS

    -- =========================

    CHECK (

        escalation_risk = FALSE

        OR (escalation_risk = TRUE AND why_flagged IS NOT NULL)

    )

);

CREATE TABLE city_insights (

    city_id INT PRIMARY KEY REFERENCES cities(id) ON DELETE CASCADE,



    -- AGGREGATED METRICS (0–1)

    avg_quality_score DECIMAL(5,4),

    avg_sop_state_compliance_score DECIMAL(5,4),

    avg_sentiment_stabilization_score DECIMAL(5,4),

    avg_escalation_rate DECIMAL(5,4),



    -- VOLUME

    total_calls INT,

    total_emergencies INT,

    avg_monthly_calls INT,



    calls_received_this_month INT,

    prev_month_calls_received INT,



    calls_received_today INT,

    emergencies_today INT,



    -- PREVIOUS MONTH SNAPSHOT

    prev_month_avg_quality_score DECIMAL(5,4),

    prev_month_avg_sop_state_compliance_score DECIMAL(5,4),

    prev_month_avg_sentiment_stabilization_score DECIMAL(5,4),

    prev_month_avg_escalation_rate DECIMAL(5,4),



    -- LLM OPS INSIGHTS

    daily_ops_insight TEXT,

    latest_month_insight TEXT,

    overall_city_insight TEXT,

    ops_insight_text TEXT,

    coaching_focus_for_city TEXT,



    key_operational_risks TEXT[],

    insight_history JSONB DEFAULT '[]'::jsonb,



    last_updated_at TIMESTAMP DEFAULT NOW()

);