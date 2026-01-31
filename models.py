from sqlalchemy import Column, Integer, String, Text, DECIMAL, TIMESTAMP, UUID, ForeignKey, ARRAY, CheckConstraint, Boolean
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid as uuid_lib

Base = declarative_base()

class City(Base):
    __tablename__ = 'cities'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False, unique=True)
    state = Column(String(100))
    
    # Relationships
    calls = relationship("Call", back_populates="city")
    city_insight = relationship("CityInsight", back_populates="city", uselist=False)


class Agent(Base):
    __tablename__ = 'agents'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    # BASIC INFO
    name = Column(String(150), nullable=False)
    employee_id = Column(String(50), unique=True)
    languages = Column(ARRAY(Text))
    
    # CURRENT METRICS (0–1)
    current_quality_score = Column(DECIMAL(5, 4), default=0.0)
    current_sop_state_compliance_score = Column(DECIMAL(5, 4), default=0.0)
    current_sentiment_stabilization_score = Column(DECIMAL(5, 4), default=0.0)
    current_escalation_rate = Column(DECIMAL(5, 4), default=0.0)
    
    calls_handled_total = Column(Integer, default=0)
    total_emergencies_count = Column(Integer, default=0)
    
    # DAILY SNAPSHOT
    calls_handled_today = Column(Integer, default=0)
    emergencies_today = Column(Integer, default=0)
    
    # PREVIOUS MONTH SNAPSHOT
    prev_month_quality_score = Column(DECIMAL(5, 4))
    prev_month_sop_state_compliance_score = Column(DECIMAL(5, 4))
    prev_month_sentiment_stabilization_score = Column(DECIMAL(5, 4))
    prev_month_escalation_rate = Column(DECIMAL(5, 4))
    prev_month_calls_handled = Column(Integer)
    prev_month_emergencies = Column(Integer)
    
    # LLM INSIGHTS
    latest_month_insight = Column(Text)
    overall_insight_text = Column(Text)
    latest_change_summary = Column(Text)

    
    # MEMORY / TRENDS
    insight_history = Column(JSONB, default=list)
    recent_trend_array = Column(JSONB, default=list)
    

    
    last_insight_generated_at = Column(TIMESTAMP)
    last_updated_at = Column(TIMESTAMP, default=datetime.now)
    
    # Relationships
    calls = relationship("Call", back_populates="agent")


class Call(Base):
    __tablename__ = 'calls'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid_lib.uuid4)
    
    agent_id = Column(UUID(as_uuid=True), ForeignKey('agents.id', ondelete='SET NULL'))
    city_id = Column(Integer, ForeignKey('cities.id', ondelete='SET NULL'))
    
    customer_phone = Column(String(20))
    customer_name = Column(String(100))
    customer_preferred_language = Column(String(50))
    
    audio_url = Column(Text, nullable=False)
    duration_seconds = Column(Integer)
    
    call_timestamp = Column(TIMESTAMP(timezone=True), default=datetime.now)
    
    call_context = Column(String(30), nullable=False)
    
    primary_issue_category = Column(String(50))
    agent_manual_note = Column(Text)
    
    processing_status = Column(String(20), default='pending')
    
    __table_args__ = (
        CheckConstraint(
            "call_context IN ('NEW_ISSUE', 'FOLLOW_UP', 'ONGOING_CASE', 'REOPENED', 'INFORMATION_ONLY', 'CLOSED_ISSUE')",
            name='check_call_context'
        ),
        CheckConstraint(
            "processing_status IN ('pending', 'transcribed', 'analyzed', 'failed')",
            name='check_processing_status'
        ),
    )
    
    # Relationships
    agent = relationship("Agent", back_populates="calls")
    city = relationship("City", back_populates="calls")
    insight = relationship("CallInsight", back_populates="call", uselist=False)


class CallInsight(Base):
    __tablename__ = 'call_insights'
    
    call_id = Column(UUID(as_uuid=True), ForeignKey('calls.id', ondelete='CASCADE'), primary_key=True)
    
    transcript = Column(Text)
    language_spoken = Column(String(50))
    
    # CORE SCORES (0–1)
    sop_state_compliance_score = Column(DECIMAL(5, 4), nullable=False)
    conversation_control_score = Column(DECIMAL(5, 4), nullable=False)
    sentiment_stabilization_score = Column(DECIMAL(3, 2), nullable=False)
    resolution_path_validity_score = Column(DECIMAL(3, 2), nullable=False)
    
    # DERIVED CALL QUALITY
    overall_call_quality_score = Column(DECIMAL(5, 4), nullable=False)
    
    # ESCALATION SIGNAL
    escalation_risk = Column(Boolean, nullable=False)
    why_flagged = Column(Text)
    
    # HUMAN INTERVENTION
    human_remarks = Column(Text)
    
    # LLM INSIGHTS
    business_insight = Column(Text)
    coaching_insight = Column(Text)
    
    created_at = Column(TIMESTAMP, default=datetime.now)
    
    __table_args__ = (
        CheckConstraint("sop_state_compliance_score BETWEEN 0 AND 1", name='check_sop_score'),
        CheckConstraint("conversation_control_score BETWEEN 0 AND 1", name='check_conversation_score'),
        CheckConstraint("sentiment_stabilization_score IN (0, 0.5, 1)", name='check_sentiment_score'),
        CheckConstraint("resolution_path_validity_score IN (0, 0.75, 1)", name='check_resolution_score'),
        CheckConstraint("overall_call_quality_score BETWEEN 0 AND 1", name='check_quality_score'),
        CheckConstraint(
            "escalation_risk = FALSE OR (escalation_risk = TRUE AND why_flagged IS NOT NULL)",
            name='check_escalation_flag'
        ),
    )
    
    # Relationships
    call = relationship("Call", back_populates="insight")


class CityInsight(Base):
    __tablename__ = 'city_insights'
    
    city_id = Column(Integer, ForeignKey('cities.id', ondelete='CASCADE'), primary_key=True)
    
    # AGGREGATED METRICS (0–1)
    avg_quality_score = Column(DECIMAL(5, 4))
    avg_sop_state_compliance_score = Column(DECIMAL(5, 4))
    avg_sentiment_stabilization_score = Column(DECIMAL(5, 4))
    avg_escalation_rate = Column(DECIMAL(5, 4))
    
    # VOLUME
    total_calls = Column(Integer)
    total_emergencies = Column(Integer)
    avg_monthly_calls = Column(Integer)
    
    calls_received_this_month = Column(Integer)
    prev_month_calls_received = Column(Integer)
    
    calls_received_today = Column(Integer)
    emergencies_today = Column(Integer)
    
    # PREVIOUS MONTH SNAPSHOT
    prev_month_avg_quality_score = Column(DECIMAL(5, 4))
    prev_month_avg_sop_state_compliance_score = Column(DECIMAL(5, 4))
    prev_month_avg_sentiment_stabilization_score = Column(DECIMAL(5, 4))
    prev_month_avg_escalation_rate = Column(DECIMAL(5, 4))
    
    # LLM OPS INSIGHTS
    daily_ops_insight = Column(Text)
    latest_month_insight = Column(Text)
    overall_city_insight = Column(Text)
    ops_insight_text = Column(Text)
    coaching_focus_for_city = Column(Text)
    
    key_operational_risks = Column(ARRAY(Text))
    insight_history = Column(JSONB, default=list)
    


    last_insight_generated_at = Column(TIMESTAMP)
    last_updated_at = Column(TIMESTAMP, default=datetime.now)
    
    # Relationships
    city = relationship("City", back_populates="city_insight")
