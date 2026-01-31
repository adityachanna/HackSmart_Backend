from sqlalchemy.orm import Session
from models import Call, Agent
from typing import Dict, Any, Optional
from datetime import datetime
import requests
import json
import os

AI_AGENT_URL = "https://hacksmartagent26-698063521469.asia-south1.run.app/agent"

def process_call_for_ai_evaluation(db: Session, call_id: str) -> Dict[str, Any]:
    """
    Processes a call after ingestion by:
    1. Fetching call data and AWS URL from database
    2. Getting agent language information
    3. Preparing metadata for AI evaluation
    4. Sending data to External AI Agent
    5. Saving output to local JSON
    
    Args:
        db: Database session
        call_id: UUID of the call to process
        
    Returns:
        Dict containing status and prepared metadata
    """
    
    # Fetch the call from database
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        return {
            "status": "error",
            "message": f"Call with ID {call_id} not found"
        }
    
    # Fetch agent information to get languages
    agent = None
    agent_languages = []
    if call.agent_id:
        agent = db.query(Agent).filter(Agent.id == call.agent_id).first()
        if agent and agent.languages:
            # Send all languages as a list
            agent_languages = agent.languages if isinstance(agent.languages, list) else [str(agent.languages)]
    
    # Prepare metadata for AI evaluation
    # Note: Excludes customer PII (name, phone) and duration for privacy/security
    metadata = {
        "call_id": str(call.id),
        "agent_id": str(call.agent_id) if call.agent_id else "",
        "primary_issue_category": call.primary_issue_category if call.primary_issue_category else "unknown",
        "agent_languages": agent_languages,  # List of all languages
        "call_timestamp": call.call_timestamp.isoformat() if call.call_timestamp else "",
        "call_context": call.call_context,
        "agent_manual_note": call.agent_manual_note,
        "customer_preferred_language": call.customer_preferred_language if call.customer_preferred_language else "",
        "audio_url": call.audio_url,  # AWS S3 URL
        "city_id": call.city_id
    }
    
    print(f"📋 Prepared metadata for call {call_id}:")
    print(f"   - Agent: {metadata['agent_id']}")
    print(f"   - Issue: {metadata['primary_issue_category']}")
    print(f"   - Languages: {metadata['agent_languages']}")
    print(f"   - Audio URL: {metadata['audio_url']}")
    
    # ---------------------------------------------------------
    # EXTERNAL AI AGENT INTEGRATION
    # ---------------------------------------------------------
    try:
        # Prepare payload for x-www-form-urlencoded
        payload = {
            "audio_url": metadata["audio_url"],
            "call_id": metadata["call_id"],
            "agent_id": metadata["agent_id"],
            "primary_issue_category": metadata["primary_issue_category"],
            "customer_language_preference": metadata["customer_preferred_language"],
            "call_timestamp": metadata["call_timestamp"]
        }
        
        print(f"🚀 Sending request to AI Agent: {AI_AGENT_URL}")
        response = requests.post(AI_AGENT_URL, data=payload) # requests handles form-urlencoded by default with data=dict
        
        # Check response
        if response.status_code == 200:
            ai_output = response.json()
            print("✅ AI Agent response received.")
            
            # 1. Update/Create CallInsight in Database
            from models import CallInsight
            
            # Extract scores safely
            scores = ai_output.get("scores", {})
            insights = ai_output.get("insights", {})
            metadata_res = ai_output.get("metadata", {})
            
            # Check if insight already exists
            call_insight = db.query(CallInsight).filter(CallInsight.call_id == call_id).first()
            if not call_insight:
                call_insight = CallInsight(call_id=call_id)
                db.add(call_insight)
            
            # Maps fields from API response to DB model
            call_insight.sop_compliance_score = float(scores.get("sop_compliance", 0.0))
            
            # Mapping specific fields
            call_insight.communication_score = float(scores.get("communication", 0.0))
            call_insight.sentiment_stabilization_score = float(scores.get("sentiment_stabilization", 0.0))
            call_insight.resolution_validity_score = float(scores.get("resolution_validity", 0.0))
            call_insight.overall_quality_score = float(scores.get("overall_quality", 0.0))
            call_insight.coaching_priority = float(scores.get("coaching_priority", 0.0))
            
            # Escalation
            esc_risk = float(scores.get("escalation_risk", 0.0))
            call_insight.escalation_risk = True if esc_risk > 0.5 else False
            
            # JSONB fields
            call_insight.issue_analysis = ai_output.get("issue_analysis", {})
            call_insight.resolution_analysis = ai_output.get("resolution_analysis", {})
            call_insight.sop_deviations = ai_output.get("sop_deviations", [])
            call_insight.sentiment_trajectory = ai_output.get("sentiment_trajectory", [])
            
            # Text fields
            call_insight.business_insight = insights.get("business_insight", "")
            call_insight.coaching_insight = insights.get("agent_summary", "") # Mapping summary to coaching insight
            
            # Update Call Status and Language
            call.processing_status = 'analyzed'
            call_insight.language_spoken = metadata_res.get("detected_language", "unknown")
            
            db.commit()
            print(f"💾 Call Insights saved to DB for {call_id}")
            
            return {
                "status": "success",
                "message": "AI processing completed and saved to DB.",
                "call_id": str(call_id),
                "ai_output": ai_output
            }
            
        else:
            print(f"❌ AI Agent failed with status {response.status_code}: {response.text}")
            call.processing_status = 'failed'
            db.commit()
            return {
                "status": "error", 
                "message": f"AI Agent Error: {response.text}",
                "call_id": str(call_id)
            }

    except Exception as e:
        import traceback
        traceback.print_exc()
        return {
            "status": "error",
            "message": f"Integration failed: {str(e)}"
        }

def get_call_processing_status(db: Session, call_id: str) -> Dict[str, Any]:
    """
    Check the processing status of a call.
    """
    call = db.query(Call).filter(Call.id == call_id).first()
    
    if not call:
        return {
            "status": "error",
            "message": f"Call with ID {call_id} not found"
        }
    
    return {
        "status": "success",
        "call_id": str(call.id),
        "processing_status": call.processing_status,
        "audio_url": call.audio_url
    }
