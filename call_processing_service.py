from sqlalchemy.orm import Session
from models import Call, Agent
from typing import Dict, Any, Optional
from datetime import datetime

def process_call_for_ai_evaluation(db: Session, call_id: str) -> Dict[str, Any]:
    """
    Processes a call after ingestion by:
    1. Fetching call data and AWS URL from database
    2. Getting agent language information
    3. Preparing metadata for AI evaluation
    4. Updating status to "processing"
    
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
        "agent_id": str(call.agent_id) if call.agent_id else None,
        "primary_issue_category": call.primary_issue_category,
        "agent_languages": agent_languages,  # List of all languages
        "call_timestamp": call.call_timestamp.isoformat() if call.call_timestamp else None,
        "call_context": call.call_context,
        "agent_manual_note": call.agent_manual_note,
        "customer_preferred_language": call.customer_preferred_language,
        "audio_url": call.audio_url,  # AWS S3 URL
        "city_id": call.city_id
    }
    
    # Note: Status remains 'pending' (the default)
    # Valid statuses per schema: 'pending', 'transcribed', 'analyzed', 'failed'
    # When AI transcription completes, update to 'transcribed'
    # When AI analysis completes, update to 'analyzed'
    
    print(f"📋 Prepared metadata for call {call_id}:")
    print(f"   - Agent: {metadata['agent_id']}")
    print(f"   - Issue: {metadata['primary_issue_category']}")
    print(f"   - Languages: {metadata['agent_languages']}")
    print(f"   - Audio URL: {metadata['audio_url']}")
    print(f"   - Status: {call.processing_status} (ready for AI processing)")
    
    # TODO: In future, send this metadata to AI evaluation service
    # AI service will:
    # 1. Transcribe audio -> update status to 'transcribed'
    # 2. Analyze call -> update status to 'analyzed'
    # 3. If error occurs -> update status to 'failed'
    
    return {
        "status": "success",
        "message": "Call metadata prepared for AI processing",
        "call_id": str(call_id),
        "metadata": metadata,
        "processing_status": call.processing_status,
        "next_step": "AI transcription and evaluation (not implemented yet)"
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
