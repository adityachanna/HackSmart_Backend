from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Depends
from pydantic import BaseModel
from typing import Optional
import base64
import shutil
import os
import tempfile
import uuid
from mutagen.mp3 import MP3
from call_engestion import ingest_call
from dotenv import load_dotenv
from sqlalchemy.orm import Session, sessionmaker
from connection import engine
from dashboard_service import get_india_map_dashboard_data
from leaderboard_service import get_agent_leaderboard_data, get_agent_details_data, search_agents
from city_service import get_city_details_data, get_cities_list
from call_processing_service import process_call_for_ai_evaluation, get_call_processing_status

load_dotenv()

# Create SessionLocal class for database sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

app = FastAPI(title="HackSmart Call Ingestion API")

# Dependency to get database session
def get_db():
    """Database session dependency"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================
# FEATURE 1: India Risk Map & Dashboard
# ============================================

@app.get("/api/dashboard/india-map")
async def get_india_risk_map(db: Session = Depends(get_db)):
    """
    Feature 1: India Risk Map & Dashboard
    
    Returns risk status, SOP scores, and call volume data grouped by state.
    
    Response:
    {
        "status": "success",
        "data": [
            {
                "state": "Delhi",
                "overall_sop_score": 0.86,
                "total_call_volume_pct": 35.0,
                "top_issue": "Battery Pick-Up Request",
                "cities": [
                    {
                        "id": 1,
                        "name": "New Delhi",
                        "sop_score": 0.86
                    }
                ]
            },
            ...
        ]
    }
    """
    try:
        return get_india_map_dashboard_data(db)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch dashboard data: {str(e)}"
        )

# ============================================
# FEATURE 2: The Leaderboard
# ============================================

@app.get("/api/agents/leaderboard")
async def get_agent_leaderboard(db: Session = Depends(get_db)):
    """
    Feature 2: The Leaderboard
    
    Returns a ranked list of agents based on their overall quality score.
    
    Response:
    {
      "status": "success",
      "data": [
        {
          "rank": 1,
          "agent_id": "uuid",
          "name": "Agent Name",
          "overall_score": 0.9450,
          "calls_received": 620,
          "emergencies": 2
        },
        ...
      ]
    }
    """
    try:
        return get_agent_leaderboard_data(db)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch leaderboard data: {str(e)}"
        )

# ============================================
# FEATURE 4: Agent Wise Details
# ============================================

@app.get("/api/agents/search")
async def search_agents_endpoint(query: str, db: Session = Depends(get_db)):
    """
    Search for agents by name or ID.
    
    Query Parameters:
    - query: Search string (partial match on name or employee_id)
    
    Response:
    {
      "status": "success",
      "data": [
        {
          "agent_id": "uuid",
          "name": "Name",
          "employee_id": "ID",
          "overall_score": 0.95
        },
        ...
      ]
    }
    """
    try:
        if not query:
            raise HTTPException(status_code=400, detail="Query parameter is required")
            
        return search_agents(db, query)
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to search agents: {str(e)}"
        )

@app.get("/api/agents/{agent_id}/stats")
async def get_agent_stats(agent_id: str, db: Session = Depends(get_db)):
    """
    Feature 4: Detailed Agent Stats
    
    Returns comprehensive data for a specific agent.
    
    Response:
    {
      "status": "success",
      "data": {
        "agent_profile": { ... },
        "current_stats": { ... },
        "history_comparison": { ... },
        "trend_data": [ ... ],
        "llm_insights": { ... }
      }
    }
    """
    try:
        result = get_agent_details_data(db, agent_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"Agent with ID {agent_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch agent stats: {str(e)}"
        )

# ============================================
# FEATURE 3: City Wise Details
# ============================================

@app.get("/api/cities")
async def get_all_cities(db: Session = Depends(get_db)):
    """
    Get a list of all available cities.
    
    Response:
    {
      "status": "success",
      "data": [
        {
          "id": 1,
          "name": "New Delhi",
          "state": "Delhi"
        },
        ...
      ]
    }
    """
    try:
        return get_cities_list(db)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch cities list: {str(e)}"
        )

@app.get("/api/cities/{city_id}")
async def get_city_details(city_id: int, db: Session = Depends(get_db)):
    """
    Feature 3: Detailed City Metrics & Insights
    
    Returns comprehensive data for a specific city.
    
    Response:
    {
      "status": "success",
      "data": {
        "city_info": { ... },
        "metrics": { ... },
        "volume": { ... },
        "llm_insights": { ... },
        "operational_risks": [ ... ]
      }
    }
    """
    try:
        result = get_city_details_data(db, city_id)
        if not result:
            raise HTTPException(status_code=404, detail=f"City with ID {city_id} not found")
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to fetch city details: {str(e)}"
        )

# ============================================
# Call Ingestion Endpoint
# ============================================


@app.post("/ingest/call")
async def ingest_call_endpoint(
    file: UploadFile = File(..., description="MP3 Audio File"),
    agent_identifier: str = Form(..., description="Agent Name, Employee ID, or UUID"),
    issue_category: str = Form(..., description="Primary issue category"),
    city_identifier: str = Form(..., description="City Name or ID (1-6)"),
    customer_name: Optional[str] = Form(None),
    customer_phone: Optional[str] = Form(None),
    call_context: Optional[str] = Form(None),
    agent_manual_note: Optional[str] = Form(None)
):
    """
    Ingest a call recording (MP3 file upload).
    
    - Accepts standard file upload (multipart/form-data)
    - Automatically calculates audio duration
    - Uploads to S3
    - Stores metadata in database
    """
    temp_file_path = None
    try:
        # Validate file type
        if not file.filename.lower().endswith('.mp3'):
             raise HTTPException(status_code=400, detail="Only MP3 files are supported")

        # Create a temporary file to save the uploaded audio
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as temp_file:
            shutil.copyfileobj(file.file, temp_file)
            temp_file_path = temp_file.name

        # Calculate Duration using Mutagen
        try:
            audio = MP3(temp_file_path)
            duration_seconds = int(audio.info.length)
            print(f"Calculated Duration: {duration_seconds} seconds")
        except Exception as e:
            print(f"Warning: Could not calculate duration: {e}")
            duration_seconds = 0

        # Read file as base64 for the ingest function
        # (Since our ingest_call function supports base64, we can reuse that logic 
        # OR just pass the file path since we have it on disk now. 
        # Passing file path is more efficient than reading into memory as base64.)
        
        call_id = ingest_call(
            mp3_path=temp_file_path,  # Use the temp file path directly
            agent_identifier=agent_identifier,
            issue_category=issue_category,
            city_identifier=city_identifier,
            customer_name=customer_name,
            customer_phone=customer_phone,
            call_context=call_context,
            duration_seconds=duration_seconds, # Pass the calculated duration
            agent_manual_note=agent_manual_note
        )
        
        # Trigger processing for AI evaluation
        # Get a new db session for processing
        db = SessionLocal()
        try:
            processing_result = process_call_for_ai_evaluation(db, str(call_id))
            print(f"✅ Call processing initiated: {processing_result.get('message')}")
        except Exception as proc_error:
            print(f"⚠️ Warning: Could not initiate processing: {proc_error}")
            # Don't fail the ingestion if processing fails
        finally:
            db.close()
        
        return {
            "status": "success",
            "message": "Call ingested successfully and queued for processing",
            "call_id": str(call_id),
            "media_info": {
                "filename": file.filename,
                "duration_seconds": duration_seconds
            }
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {str(e)}")
    finally:
        # Clean up the temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
            except Exception:
                pass

# ============================================
# Call Processing Endpoints
# ============================================

@app.post("/api/calls/{call_id}/process")
async def trigger_call_processing(call_id: str, db: Session = Depends(get_db)):
    """
    Manually trigger AI processing for a specific call.
    
    This prepares the call metadata and updates status to 'processing'.
    In the future, this will trigger actual AI evaluation.
    """
    try:
        result = process_call_for_ai_evaluation(db, call_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process call: {str(e)}"
        )

@app.get("/api/calls/{call_id}/status")
async def get_call_status(call_id: str, db: Session = Depends(get_db)):
    """
    Check the processing status of a call.
    """
    try:
        result = get_call_processing_status(db, call_id)
        if result.get("status") == "error":
            raise HTTPException(status_code=404, detail=result.get("message"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get call status: {str(e)}"
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend:app", host="0.0.0.0", port=8000, reload=True)
