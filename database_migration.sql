-- =====================================================
-- MIGRATION SCRIPT: Update column names to match new AI API
-- =====================================================
-- Run these queries in your Supabase SQL editor in order

-- =====================================================
-- 1. ALTER call_insights TABLE
-- =====================================================

-- Rename columns
ALTER TABLE call_insights 
    RENAME COLUMN sop_state_compliance_score TO sop_compliance_score;

ALTER TABLE call_insights 
    RENAME COLUMN resolution_path_validity_score TO resolution_validity_score;

ALTER TABLE call_insights 
    RENAME COLUMN overall_call_quality_score TO overall_quality_score;

-- Drop the conversation_control_score column (not in new API)
ALTER TABLE call_insights 
    DROP COLUMN conversation_control_score;

-- Add new columns for AI analysis
ALTER TABLE call_insights 
    ADD COLUMN communication_score DECIMAL(5,4);

ALTER TABLE call_insights 
    ADD COLUMN coaching_priority DECIMAL(5,4);

ALTER TABLE call_insights 
    ADD COLUMN issue_analysis JSONB;

ALTER TABLE call_insights 
    ADD COLUMN resolution_analysis JSONB;

ALTER TABLE call_insights 
    ADD COLUMN sop_deviations JSONB;

ALTER TABLE call_insights 
    ADD COLUMN sentiment_trajectory JSONB;

-- Update constraints to match renamed columns
-- Drop old constraints
ALTER TABLE call_insights 
    DROP CONSTRAINT IF EXISTS check_sop_score;

ALTER TABLE call_insights 
    DROP CONSTRAINT IF EXISTS check_conversation_score;

ALTER TABLE call_insights 
    DROP CONSTRAINT IF EXISTS check_resolution_score;

ALTER TABLE call_insights 
    DROP CONSTRAINT IF EXISTS check_quality_score;

-- Add new constraints
ALTER TABLE call_insights 
    ADD CONSTRAINT check_sop_score 
    CHECK (sop_compliance_score BETWEEN 0 AND 1);

ALTER TABLE call_insights 
    ADD CONSTRAINT check_resolution_score 
    CHECK (resolution_validity_score IN (0, 0.75, 1));

ALTER TABLE call_insights 
    ADD CONSTRAINT check_quality_score 
    CHECK (overall_quality_score BETWEEN 0 AND 1);

-- =====================================================
-- 2. ALTER agents TABLE
-- =====================================================

ALTER TABLE agents 
    RENAME COLUMN current_sop_state_compliance_score TO current_sop_compliance_score;

ALTER TABLE agents 
    RENAME COLUMN prev_month_sop_state_compliance_score TO prev_month_sop_compliance_score;

-- =====================================================
-- 3. ALTER city_insights TABLE
-- =====================================================

ALTER TABLE city_insights 
    RENAME COLUMN avg_sop_state_compliance_score TO avg_sop_compliance_score;

ALTER TABLE city_insights 
    RENAME COLUMN prev_month_avg_sop_state_compliance_score TO prev_month_avg_sop_compliance_score;

-- =====================================================
-- VERIFICATION QUERIES
-- =====================================================
-- Run these to verify the changes were successful

-- Check call_insights structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'call_insights' 
ORDER BY ordinal_position;

-- Check agents structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'agents' 
AND column_name LIKE '%sop%'
ORDER BY ordinal_position;

-- Check city_insights structure
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'city_insights' 
AND column_name LIKE '%sop%'
ORDER BY ordinal_position;
