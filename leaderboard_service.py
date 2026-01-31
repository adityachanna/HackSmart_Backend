from sqlalchemy.orm import Session
from sqlalchemy import desc
from models import Agent
from typing import List, Dict, Any

def get_agent_leaderboard_data(db: Session) -> Dict[str, Any]:
    """
    Feature 2: The Leaderboard
    
    Returns a list of agents sorted by overall score (descending).
    
    Response format:
    {
      "status": "success",
      "data": [
        {
          "rank": 1,
          "agent_id": "uuid",
          "name": "Name",
          "overall_score": 0.9450,
          "calls_received": 620,
          "emergencies": 2
        },
        ...
      ]
    }
    """
    # Query agents and sort by current_quality_score in descending order
    # If scores are equal, we can use calls_handled_total as tie-breaker (more calls = better if scores same)
    agents = db.query(Agent).order_by(
        desc(Agent.current_quality_score), 
        desc(Agent.calls_handled_total)
    ).all()
    
    leaderboard_data = []
    
    for index, agent in enumerate(agents):
        agent_data = {
            "rank": index + 1,
            "agent_id": str(agent.id),
            "name": agent.name,
            "overall_score": float(agent.current_quality_score) if agent.current_quality_score is not None else 0.0,
            "calls_received": agent.calls_handled_total if agent.calls_handled_total is not None else 0,
            "emergencies": agent.total_emergencies_count if agent.total_emergencies_count is not None else 0
        }
        leaderboard_data.append(agent_data)
        
    return {
        "status": "success",
        "data": leaderboard_data
    }


def get_agent_details_data(db: Session, agent_id: str) -> Dict[str, Any]:
    """
    Feature 4: Detailed Agent Stats
    
    Fetches comprehensive data for a specific agent.
    """
    # Query agent
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    
    if not agent:
        return None
        
    # Helper to safe convert decimal to float
    def to_float(val):
        return float(val) if val is not None else 0.0

    # Calculate trends
    # Simple logic: If current > prev -> "up", else if current < prev -> "down", else "stable"
    def get_trend(curr, prev):
        c = to_float(curr)
        p = to_float(prev)
        if c > p: return "up"
        if c < p: return "down"
        return "stable"

    # We will generate trend objects for key metrics
    trend_data = []
    
    # 1. Quality Score Trend
    trend_data.append({
        "metric": "quality_score",
        "trend": get_trend(agent.current_quality_score, agent.prev_month_quality_score),
        "value": to_float(agent.current_quality_score),
        "prev_value": to_float(agent.prev_month_quality_score)
    })
    
    # 2. SOP Compliance Trend
    trend_data.append({
        "metric": "sop_compliance",
        "trend": get_trend(agent.current_sop_compliance_score, agent.prev_month_sop_compliance_score),
        "value": to_float(agent.current_sop_compliance_score),
        "prev_value": to_float(agent.prev_month_sop_compliance_score)
    })
    
    # 3. Sentiment Trend
    trend_data.append({
        "metric": "sentiment_stabilization",
        "trend": get_trend(agent.current_sentiment_stabilization_score, agent.prev_month_sentiment_stabilization_score),
        "value": to_float(agent.current_sentiment_stabilization_score),
        "prev_value": to_float(agent.prev_month_sentiment_stabilization_score)
    })
    
    # 4. Escalation Rate Trend (Note: "down" is usually good here, but physically it is moving down)
    trend_data.append({
        "metric": "escalation_rate",
        "trend": get_trend(agent.current_escalation_rate, agent.prev_month_escalation_rate),
        "value": to_float(agent.current_escalation_rate),
        "prev_value": to_float(agent.prev_month_escalation_rate)
    })

    data = {
        "agent_profile": {
            "id": str(agent.id),
            "name": agent.name,
            "employee_id": agent.employee_id,
            "languages": agent.languages if agent.languages else []
        },
        "current_stats": {
            "quality_score": to_float(agent.current_quality_score),
            "sop_compliance": to_float(agent.current_sop_compliance_score),
            "sentiment_stabilization": to_float(agent.current_sentiment_stabilization_score),
            "escalation_rate": to_float(agent.current_escalation_rate),
            "calls_handled_today": agent.calls_handled_today or 0,
            "emergencies_today": agent.emergencies_today or 0,
            "calls_handled_total": agent.calls_handled_total or 0,
            "total_emergencies_count": agent.total_emergencies_count or 0
        },
        "previous_month_stats": {
            "quality_score": to_float(agent.prev_month_quality_score),
            "sop_compliance": to_float(agent.prev_month_sop_compliance_score),
            "sentiment_stabilization": to_float(agent.prev_month_sentiment_stabilization_score),
            "escalation_rate": to_float(agent.prev_month_escalation_rate),
            "calls_handled": agent.prev_month_calls_handled or 0,
            "emergencies": agent.prev_month_emergencies or 0
        },
        "trend_data": trend_data,
        "llm_insights": {
            "latest_month_insight": agent.latest_month_insight,
            "overall_insight_text": agent.overall_insight_text,
            "latest_change_summary": agent.latest_change_summary
        },
        "insight_metadata": {
            "insight_history": agent.insight_history if agent.insight_history else [],
            "recent_trend_array": agent.recent_trend_array if agent.recent_trend_array else [],
            "last_insight_generated_at": agent.last_insight_generated_at.isoformat() if agent.last_insight_generated_at else None,
            "last_updated_at": agent.last_updated_at.isoformat() if agent.last_updated_at else None
        }
    }

    return {
        "status": "success",
        "data": data
    }


def search_agents(db: Session, query_str: str) -> Dict[str, Any]:
    """
    Search for agents by name or employee_id (case-insensitive partial match).
    """
    if not query_str:
        return {"status": "success", "data": []}
        
    search_term = f"%{query_str}%"
    
    # partial match on name OR employee_id
    agents = db.query(Agent).filter(
        (Agent.name.ilike(search_term)) | 
        (Agent.employee_id.ilike(search_term))
    ).limit(20).all() # Limit results to avoid overload
    
    results = []
    for agent in agents:
        results.append({
            "agent_id": str(agent.id),
            "name": agent.name,
            "employee_id": agent.employee_id,
            "overall_score": float(agent.current_quality_score) if agent.current_quality_score is not None else 0.0
        })
        
    return {
        "status": "success",
        "data": results
    }
