from sqlalchemy.orm import Session
from sqlalchemy import func
from models import City, Call, CallInsight, CityInsight
from typing import List, Dict, Any
from decimal import Decimal


def get_india_map_dashboard_data(db: Session) -> Dict[str, Any]:
    """
    Feature 1: India Risk Map & Dashboard
    
    Returns:
    {
        "status": "success",
        "data": [
            {
                "state": "Delhi",
                "overall_sop_score": 0.86,
                "total_call_volume_pct": 35.0,
                "top_issue": "Battery Pick-Up Request",
                "cities": [...]
            },
            ...
        ]
    }
    """
    
    # Get total calls across all cities for percentage calculation
    total_calls_query = db.query(func.count(Call.id)).scalar()
    
    if not total_calls_query or total_calls_query == 0:
        total_calls_query = 1  # Prevent division by zero
    
    # Query all cities with their insights
    cities_data = db.query(
        City.id,
        City.name,
        City.state,
        CityInsight.avg_sop_state_compliance_score,
        CityInsight.total_calls
    ).outerjoin(
        CityInsight, City.id == CityInsight.city_id
    ).all()
    
    # Group cities by state
    states_dict = {}
    
    for city_id, city_name, state, avg_sop_score, total_calls in cities_data:
        if not state:
            continue  # Skip cities without state information
        
        # Default values if no insights available
        sop_score = float(avg_sop_score) if avg_sop_score else 0.0
        call_count = total_calls if total_calls else 0
        
        # Get top issue for this city
        top_issue_query = db.query(
            Call.primary_issue_category,
            func.count(Call.id).label('issue_count')
        ).filter(
            Call.city_id == city_id,
            Call.primary_issue_category.isnot(None)
        ).group_by(
            Call.primary_issue_category
        ).order_by(
            func.count(Call.id).desc()
        ).first()
        
        top_issue = top_issue_query[0] if top_issue_query else "No Issues Reported"
        
        # Create city entry
        city_entry = {
            "id": city_id,
            "name": city_name,
            "sop_score": round(sop_score, 2)
        }
        
        # Group by state
        if state not in states_dict:
            states_dict[state] = {
                "state": state,
                "cities": [],
                "total_calls": 0,
                "total_sop_scores": [],
                "top_issues": {}
            }
        
        states_dict[state]["cities"].append(city_entry)
        states_dict[state]["total_calls"] += call_count
        states_dict[state]["total_sop_scores"].append(sop_score)
        
        # Count issues for state-level top issue
        if top_issue in states_dict[state]["top_issues"]:
            states_dict[state]["top_issues"][top_issue] += 1
        else:
            states_dict[state]["top_issues"][top_issue] = 1
    
    # Build final response
    result_data = []
    
    for state, state_info in states_dict.items():
        # Calculate overall SOP score for the state (average of all cities)
        if state_info["total_sop_scores"]:
            overall_sop_score = sum(state_info["total_sop_scores"]) / len(state_info["total_sop_scores"])
        else:
            overall_sop_score = 0.0
        
        # Get top issue for the state
        if state_info["top_issues"]:
            top_issue = max(state_info["top_issues"].items(), key=lambda x: x[1])[0]
        else:
            top_issue = "No Issues Reported"
        
        # Calculate call volume percentage
        call_volume_pct = (state_info["total_calls"] / total_calls_query) * 100
        
        result_data.append({
            "state": state,
            "overall_sop_score": round(overall_sop_score, 2),
            "total_call_volume_pct": round(call_volume_pct, 1),
            "top_issue": top_issue,
            "cities": state_info["cities"]
        })
    
    # Sort by call volume (descending)
    result_data.sort(key=lambda x: x["total_call_volume_pct"], reverse=True)
    
    return {
        "status": "success",
        "data": result_data
    }
