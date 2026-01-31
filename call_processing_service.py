from sqlalchemy.orm import Session
from models import Call, Agent
from typing import Dict, Any, Optional
from datetime import datetime
import requests
import json
import os

AI_AGENT_URL = "https://hacksmart-698063521469.asia-south1.run.app/agent"

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
            
            # The response has structure: { "success": bool, "transcript_text": str, "analysis": {...}, "batch_size_used": int }
            # Extract the actual analysis data
            analysis_data = ai_output.get("analysis", {})
            transcript_text = ai_output.get("transcript_text", "")
            
            # 1. Update/Create CallInsight in Database
            from models import CallInsight
            
            # Extract scores safely from analysis object
            scores = analysis_data.get("scores", {})
            insights = analysis_data.get("insights", {})
            metadata_res = analysis_data.get("metadata", {})
            
            # Check if insight already exists
            call_insight = db.query(CallInsight).filter(CallInsight.call_id == call_id).first()
            if not call_insight:
                call_insight = CallInsight(call_id=call_id)
                db.add(call_insight)
            
            # Store transcript
            call_insight.transcript = transcript_text
            
            # Helper functions to normalize scores to allowed DB values
            def normalize_sentiment_score(score):
                """Convert continuous score to discrete: 0, 0.5, or 1"""
                if score < 0.25:
                    return 0.0
                elif score < 0.75:
                    return 0.5
                else:
                    return 1.0
            
            def normalize_resolution_score(score):
                """Convert continuous score to discrete: 0, 0.75, or 1"""
                if score < 0.375:  # Closer to 0
                    return 0.0
                elif score < 0.875:  # Closer to 0.75
                    return 0.75
                else:
                    return 1.0
            
            # Maps fields from API response to DB model
            call_insight.sop_compliance_score = float(scores.get("sop_compliance", 0.0))
            
            # Mapping specific fields with normalization where needed
            call_insight.communication_score = float(scores.get("communication", 0.0))
            
            # Normalize sentiment score to allowed values (0, 0.5, 1)
            raw_sentiment = float(scores.get("sentiment_stabilization", 0.0))
            call_insight.sentiment_stabilization_score = normalize_sentiment_score(raw_sentiment)
            
            # Normalize resolution score to allowed values (0, 0.75, 1)
            raw_resolution = float(scores.get("resolution_validity", 0.0))
            call_insight.resolution_validity_score = normalize_resolution_score(raw_resolution)
            
            call_insight.overall_quality_score = float(scores.get("overall_quality", 0.0))
            call_insight.coaching_priority = float(scores.get("coaching_priority", 0.0))
            
            # Escalation
            esc_risk = float(scores.get("escalation_risk", 0.0))
            call_insight.escalation_risk = True if esc_risk > 0.5 else False
            
            # IMPORTANT: Database constraint requires why_flagged to be NOT NULL if escalation_risk is TRUE
            if call_insight.escalation_risk:
                # Try to get why_flagged from insights or generate a default reason
                call_insight.why_flagged = insights.get("why_flagged") or insights.get("business_insight") or "High escalation risk detected"
            else:
                call_insight.why_flagged = None
            
            # JSONB fields - extract from analysis object
            call_insight.issue_analysis = analysis_data.get("issue_analysis", {})
            call_insight.resolution_analysis = analysis_data.get("resolution_analysis", {})
            call_insight.sop_deviations = analysis_data.get("sop_deviations", [])
            call_insight.sentiment_trajectory = analysis_data.get("sentiment_trajectory", [])
            
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
                "ai_output": analysis_data  # Return just the analysis part for cleaner response
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
