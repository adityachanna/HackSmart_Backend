from sqlalchemy.orm import Session
from sqlalchemy import func
from models import City, CityInsight
from typing import Dict, Any, List

def get_cities_list(db: Session) -> Dict[str, Any]:
    """
    Get a list of all cities with their IDs and names.
    """
    cities = db.query(City).order_by(City.name).all()
    
    cities_data = []
    for city in cities:
        cities_data.append({
            "id": city.id,
            "name": city.name,
            "state": city.state
        })
        
    return {
        "status": "success",
        "data": cities_data
    }

def get_city_details_data(db: Session, city_id: int) -> Dict[str, Any]:
    """
    Feature 3: Detailed City Metrics & Insights
    
    Fetches comprehensive data for a specific city including:
    - Basic Info
    - Core Metrics (Current & Previous)
    - Volume Statistics
    - AI Insights
    - Operational Risks
    """
    
    # Query city and its insights
    result = db.query(City, CityInsight).outerjoin(
        CityInsight, City.id == CityInsight.city_id
    ).filter(
        City.id == city_id
    ).first()
    
    if not result:
        return None
        
    city, insight = result
    
    if not insight:
        # Return basic info if no insights exist yet
        return {
            "status": "success",
            "data": {
                "city_info": {
                    "id": city.id,
                    "name": city.name,
                    "state": city.state
                },
                "message": "No detailed insights available for this city yet."
            }
        }

    # Helper to safe convert decimal to float
    def to_float(val):
        return float(val) if val is not None else 0.0

    # derived metrics
    quality_trend = "Stable"
    if to_float(insight.avg_quality_score) > to_float(insight.prev_month_avg_quality_score):
        quality_trend = "Improving"
    elif to_float(insight.avg_quality_score) < to_float(insight.prev_month_avg_quality_score):
        quality_trend = "Declining"

    # Volume growth calculation
    current_vol = insight.calls_received_this_month or 0
    prev_vol = insight.prev_month_calls_received or 0
    volume_growth_pct = 0.0
    if prev_vol > 0:
        volume_growth_pct = ((current_vol - prev_vol) / prev_vol) * 100

    data = {
        "city_info": {
            "id": city.id,
            "name": city.name,
            "state": city.state
        },
        "metrics": {
            "avg_quality_score": to_float(insight.avg_quality_score),
            "avg_sop_compliance": to_float(insight.avg_sop_compliance_score),
            "avg_sentiment_score": to_float(insight.avg_sentiment_stabilization_score),
            "avg_escalation_rate": to_float(insight.avg_escalation_rate),
            
            # Comparison Data
            "prev_month_quality": to_float(insight.prev_month_avg_quality_score),
            "prev_month_sop": to_float(insight.prev_month_avg_sop_compliance_score),
            "prev_month_sentiment": to_float(insight.prev_month_avg_sentiment_stabilization_score),
            "prev_month_escalation": to_float(insight.prev_month_avg_escalation_rate),
            
            # Derived
            "quality_trend": quality_trend
        },
        "volume": {
            "total_calls_today": insight.calls_received_today or 0,
            "total_emergencies_today": insight.emergencies_today or 0,
            "monthly_volume": current_vol,
            "prev_monthly_volume": prev_vol,
            "volume_growth_pct": round(volume_growth_pct, 1)
        },
        "llm_insights": {
            "daily_ops_insight": insight.daily_ops_insight,
            "latest_month_insight": insight.latest_month_insight,
            "overall_city_insight": insight.overall_city_insight,
            "coaching_focus": insight.coaching_focus_for_city
        },
        "operational_risks": insight.key_operational_risks if insight.key_operational_risks else []
    }

    return {
        "status": "success",
        "data": data
    }
