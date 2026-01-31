from sqlalchemy.orm import Session
from models import Call, CallInsight, Agent, City
from datetime import datetime, timedelta
from typing import Dict, Any, List

def get_escalatory_calls(db: Session) -> Dict[str, Any]:
    """
    Fetches all calls from the last 5 minutes where escalation_risk > 0.5.
    Returns detailed call information including agent, analysis, and SOP deviations.
    
    Args:
        db: Database session
        
    Returns:
        Dict containing flagged calls with full analysis
    """
    
    # Calculate time window (last 5 minutes)
    now = datetime.now()
    five_mins_ago = now - timedelta(minutes=5)
    
    # Query for recent calls with high escalation risk
    # Join Call with CallInsight to get escalation_risk score
    flagged_calls = db.query(Call, CallInsight, Agent, City).join(
        CallInsight, Call.id == CallInsight.call_id
    ).outerjoin(
        Agent, Call.agent_id == Agent.id
    ).outerjoin(
        City, Call.city_id == City.id
    ).filter(
        Call.call_timestamp >= five_mins_ago,
        CallInsight.escalation_risk == True  # Boolean flag
    ).order_by(Call.call_timestamp.desc()).all()
    
    # Format response
    escalatory_calls = []
    
    for call, insight, agent, city in flagged_calls:
        # Calculate escalation score from JSONB or use the boolean
        # The API returns escalation_risk as a score (0-1), we stored it as boolean
        # But we can look at coaching_priority or other metrics
        
        call_data = {
            "call_id": str(call.id),
            "call_timestamp": call.call_timestamp.isoformat() if call.call_timestamp else None,
            "audio_url": call.audio_url,
            "duration_seconds": call.duration_seconds,
            "processing_status": call.processing_status,
            "primary_issue_category": call.primary_issue_category,
            "customer_preferred_language": call.customer_preferred_language,
            
            # Agent Information
            "agent": {
                "agent_id": str(agent.id) if agent else None,
                "name": agent.name if agent else "Unknown",
                "employee_id": agent.employee_id if agent else None
            },
            
            # City Information
            "city": {
                "city_id": city.id if city else None,
                "name": city.name if city else "Unknown",
                "state": city.state if city else None
            },
            
            # Scores
            "scores": {
                "sop_compliance": float(insight.sop_compliance_score) if insight.sop_compliance_score else 0.0,
                "communication": float(insight.communication_score) if insight.communication_score else 0.0,
                "sentiment_stabilization": float(insight.sentiment_stabilization_score) if insight.sentiment_stabilization_score else 0.0,
                "resolution_validity": float(insight.resolution_validity_score) if insight.resolution_validity_score else 0.0,
                "overall_quality": float(insight.overall_quality_score) if insight.overall_quality_score else 0.0,
                "coaching_priority": float(insight.coaching_priority) if insight.coaching_priority else 0.0
            },
            
            # Analysis Details
            "analysis": {
                "business_insight": insight.business_insight,
                "coaching_insight": insight.coaching_insight,
                "escalation_flagged": insight.escalation_risk,
                "why_flagged": insight.why_flagged,
                "language_spoken": insight.language_spoken
            },
            
            # SOP Deviations (JSONB field)
            "sop_deviations": insight.sop_deviations if insight.sop_deviations else [],
            
            # Issue Analysis (JSONB field)
            "issue_analysis": insight.issue_analysis if insight.issue_analysis else {},
            
            # Resolution Analysis (JSONB field)
            "resolution_analysis": insight.resolution_analysis if insight.resolution_analysis else {},
            
            # Sentiment Trajectory (JSONB field)
            "sentiment_trajectory": insight.sentiment_trajectory if insight.sentiment_trajectory else []
        }
        
        escalatory_calls.append(call_data)
    
    return {
        "status": "success",
        "timestamp": now.isoformat(),
        "time_window": "last_5_minutes",
        "count": len(escalatory_calls),
        "flagged_calls": escalatory_calls
    }


def get_escalatory_calls_with_score_filter(db: Session, min_score: float = 0.5) -> Dict[str, Any]:
    """
    Alternative version: Fetches calls where coaching_priority > min_score
    (since escalation_risk in DB is boolean, we can use coaching_priority as the numeric score)
    
    Args:
        db: Database session
        min_score: Minimum coaching priority score to flag (default 0.5)
        
    Returns:
        Dict containing flagged calls with full analysis
    """
    
    # Calculate time window (last 5 minutes)
    now = datetime.now()
    five_mins_ago = now - timedelta(minutes=5)
    
    # Query for recent calls with high coaching priority (proxy for escalation score > 0.5)
    flagged_calls = db.query(Call, CallInsight, Agent, City).join(
        CallInsight, Call.id == CallInsight.call_id
    ).outerjoin(
        Agent, Call.agent_id == Agent.id
    ).outerjoin(
        City, Call.city_id == City.id
    ).filter(
        Call.call_timestamp >= five_mins_ago,
        CallInsight.coaching_priority > min_score
    ).order_by(Call.call_timestamp.desc()).all()
    
    # Format response (same as above)
    escalatory_calls = []
    
    for call, insight, agent, city in flagged_calls:
        call_data = {
            "call_id": str(call.id),
            "call_timestamp": call.call_timestamp.isoformat() if call.call_timestamp else None,
            "audio_url": call.audio_url,
            "duration_seconds": call.duration_seconds,
            "processing_status": call.processing_status,
            "primary_issue_category": call.primary_issue_category,
            "customer_preferred_language": call.customer_preferred_language,
            
            "agent": {
                "agent_id": str(agent.id) if agent else None,
                "name": agent.name if agent else "Unknown",
                "employee_id": agent.employee_id if agent else None
            },
            
            "city": {
                "city_id": city.id if city else None,
                "name": city.name if city else "Unknown",
                "state": city.state if city else None
            },
            
            "scores": {
                "sop_compliance": float(insight.sop_compliance_score) if insight.sop_compliance_score else 0.0,
                "communication": float(insight.communication_score) if insight.communication_score else 0.0,
                "sentiment_stabilization": float(insight.sentiment_stabilization_score) if insight.sentiment_stabilization_score else 0.0,
                "resolution_validity": float(insight.resolution_validity_score) if insight.resolution_validity_score else 0.0,
                "overall_quality": float(insight.overall_quality_score) if insight.overall_quality_score else 0.0,
                "coaching_priority": float(insight.coaching_priority) if insight.coaching_priority else 0.0
            },
            
            "analysis": {
                "business_insight": insight.business_insight,
                "coaching_insight": insight.coaching_insight,
                "escalation_flagged": insight.escalation_risk,
                "why_flagged": insight.why_flagged,
                "language_spoken": insight.language_spoken
            },
            
            "sop_deviations": insight.sop_deviations if insight.sop_deviations else [],
            "issue_analysis": insight.issue_analysis if insight.issue_analysis else {},
            "resolution_analysis": insight.resolution_analysis if insight.resolution_analysis else {},
            "sentiment_trajectory": insight.sentiment_trajectory if insight.sentiment_trajectory else []
        }
        
        escalatory_calls.append(call_data)
    
    return {
        "status": "success",
        "timestamp": now.isoformat(),
        "time_window": "last_5_minutes",
        "min_score_threshold": min_score,
        "count": len(escalatory_calls),
        "flagged_calls": escalatory_calls
    }


def get_agent_worst_call_past_week(db: Session, agent_id: str) -> Dict[str, Any]:
    """
    Fetches the worst call for a specific agent from the past week.
    "Worst" is defined as the call with the highest coaching_priority score.
    
    Args:
        db: Database session
        agent_id: UUID of the agent
        
    Returns:
        Dict containing the worst call with full analysis, or empty if no calls found
    """
    
    # Calculate time window (last 7 days)
    now = datetime.now()
    seven_days_ago = now - timedelta(days=7)
    
    # Query for agent's calls in the past week, ordered by coaching_priority DESC
    worst_call_query = db.query(Call, CallInsight, Agent, City).join(
        CallInsight, Call.id == CallInsight.call_id
    ).outerjoin(
        Agent, Call.agent_id == Agent.id
    ).outerjoin(
        City, Call.city_id == City.id
    ).filter(
        Call.agent_id == agent_id,
        Call.call_timestamp >= seven_days_ago,
        CallInsight.coaching_priority.isnot(None)  # Must have a score
    ).order_by(CallInsight.coaching_priority.desc()).first()
    
    if not worst_call_query:
        return {
            "status": "success",
            "timestamp": now.isoformat(),
            "time_window": "last_7_days",
            "agent_id": agent_id,
            "message": "No calls found for this agent in the past week",
            "worst_call": None
        }
    
    call, insight, agent, city = worst_call_query
    
    # Format the worst call data
    worst_call_data = {
        "call_id": str(call.id),
        "call_timestamp": call.call_timestamp.isoformat() if call.call_timestamp else None,
        "audio_url": call.audio_url,
        "duration_seconds": call.duration_seconds,
        "processing_status": call.processing_status,
        "primary_issue_category": call.primary_issue_category,
        "customer_preferred_language": call.customer_preferred_language,
        
        # Agent Information
        "agent": {
            "agent_id": str(agent.id) if agent else None,
            "name": agent.name if agent else "Unknown",
            "employee_id": agent.employee_id if agent else None
        },
        
        # City Information
        "city": {
            "city_id": city.id if city else None,
            "name": city.name if city else "Unknown",
            "state": city.state if city else None
        },
        
        # Scores
        "scores": {
            "sop_compliance": float(insight.sop_compliance_score) if insight.sop_compliance_score else 0.0,
            "communication": float(insight.communication_score) if insight.communication_score else 0.0,
            "sentiment_stabilization": float(insight.sentiment_stabilization_score) if insight.sentiment_stabilization_score else 0.0,
            "resolution_validity": float(insight.resolution_validity_score) if insight.resolution_validity_score else 0.0,
            "overall_quality": float(insight.overall_quality_score) if insight.overall_quality_score else 0.0,
            "coaching_priority": float(insight.coaching_priority) if insight.coaching_priority else 0.0
        },
        
        # Analysis Details
        "analysis": {
            "business_insight": insight.business_insight,
            "coaching_insight": insight.coaching_insight,
            "escalation_flagged": insight.escalation_risk,
            "why_flagged": insight.why_flagged,
            "language_spoken": insight.language_spoken
        },
        
        # SOP Deviations (JSONB field)
        "sop_deviations": insight.sop_deviations if insight.sop_deviations else [],
        
        # Issue Analysis (JSONB field)
        "issue_analysis": insight.issue_analysis if insight.issue_analysis else {},
        
        # Resolution Analysis (JSONB field)
        "resolution_analysis": insight.resolution_analysis if insight.resolution_analysis else {},
        
        # Sentiment Trajectory (JSONB field)
        "sentiment_trajectory": insight.sentiment_trajectory if insight.sentiment_trajectory else []
    }
    
    return {
        "status": "success",
        "timestamp": now.isoformat(),
        "time_window": "last_7_days",
        "agent_id": agent_id,
        "worst_call": worst_call_data
    }
