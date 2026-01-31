
import os
import json
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from connection import engine
from models import Agent, Call
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# Using a reliable model on OpenRouter
MODEL_NAME = "x-ai/grok-4.1-fast" 

def get_llm_response(prompt, system_prompt="You are a helpful assistant."):
    """
    Helper to call OpenRouter LLM.
    """
    if not OPENROUTER_API_KEY:
        print("Error: OPENROUTER_API_KEY not found in .env")
        return None

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3,
        "max_tokens": 1000
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content'].strip()
        else:
            print(f"LLM Error: No choices in response: {data}")
            return None
    except Exception as e:
        print(f"LLM Request Failed: {e}")
        return None

def generate_agent_monthly_insight(agent_name, calls_data):
    """
    Generates insights for the current month based on call logs.
    """
    if not calls_data:
        return "No calls recorded this month."

    calls_summary = "\n".join([
        f"- Call on {c['date']}: Coaching Insight='{c.get('coaching_insight', 'N/A')}', Human Remarks='{c.get('human_remarks', 'N/A')}'"
        for c in calls_data[:50] # Limit to last 50 calls to fit context
    ])

    prompt = f"""
    Analyze the following call logs for agent '{agent_name}' for this month.
    
    Call Logs:
    {calls_summary}
    
    Task:
    Generate a detailed monthly performance insight (100 words or less). 
    Focus on:
    1. Key strengths demonstrated.
    2. Recurring issues or weaknesses.
    3. Overall sentiment and customer satisfaction trends.
    4. Compliance with protocols.
    
    Return ONLY the insight text. Do NOT include word counts like "(150 words)" at the end. Do NOT use markdown.
    """

    return get_llm_response(prompt, system_prompt="You are a QA Supervisor for a Call Center.")

def update_overall_insight(current_overall, monthly_insight):
    """
    Merges the new monthly insight into the overall insight and generates a change summary.
    """
    
    if not current_overall:
        current_overall = "No previous history available."

    prompt = f"""
    You are updating the long-term profile of a call center agent.
    
    Current Overall Insight (Up to last month):
    "{current_overall}"
    
    New Monthly Insight (This month's performance):
    "{monthly_insight}"
    
    Task:
    1. Create an UPDATED Overall Insight that integrates the new month's findings into the historical context. 
       - If the new month confirms old trends, reinforce them.
       - If the new month shows a change (improvement or decline), reflect this evolution (e.g., "Previously struggled with X, but recently showed improvement...").
       - If the new month shows a change (improvement or decline), reflect this evolution (e.g., "Previously struggled with X, but recently showed improvement...").
       - Keep it concise (100 words or less). Do NOT include word counts like "(150 words)" at the end. Do NOT use markdown.
    
    2. Generate a 'Latest Change Summary' (50 words or less).
       - Specifically highlight what changed THIS month compared to the past.
       - distinct improvements or declines.
       - Specifically highlight what changed THIS month compared to the past.
       - distinct improvements or declines.
       - Do NOT include word counts.
       - Do NOT use markdown.
    
    Output Format:
    Please use the following exact format with separators:
    
    [OVERALL_START]
    ...updated overall text here...
    [OVERALL_END]
    
    [CHANGE_START]
    ...change summary here...
    [CHANGE_END]
    """

    response = get_llm_response(prompt)
    if not response:
        return current_overall, "Could not generate update."

    # Parse response
    try:
        overall_text = response.split("[OVERALL_START]")[1].split("[OVERALL_END]")[0].strip()
        change_text = response.split("[CHANGE_START]")[1].split("[CHANGE_END]")[0].strip()
        return overall_text, change_text
    except Exception as e:
        print(f"Error parsing LLM response: {e}. Raw response: {response[:100]}...")
        # Fallback - just try to return the raw text if parsing fails, or keep old one
        if "[OVERALL_START]" in response:
             # Try a best effort fix if one tag is missing 
             return response, "Error parsing change summary."
        return response, "Error parsing change summary."

def update_single_agent_insights(db: Session, agent_id: str):
    """
    Generates and updates insights for a single agent.
    Designed to be called from an API endpoint.
    """
    try:
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if not agent:
            return {"status": "error", "message": f"Agent {agent_id} not found."}

        print(f"Generating insights for agent: {agent.name} ({agent.id})...")
        
        now = datetime.now()
        
        # Check if already updated recently (1 Hour Cache)
        # using dedicated column now
        if agent.last_insight_generated_at:
             time_since_update = now - agent.last_insight_generated_at
             if time_since_update < timedelta(hours=1) and agent.latest_month_insight:
                 print("  - Agent insights cached (<1hr). Returning cached values.")
                 return {
                    "status": "success",
                    "message": "Insights retrieved from cache.",
                    "data": {
                        "latest_month_insight": agent.latest_month_insight,
                        "overall_insight_text": agent.overall_insight_text,
                        "latest_change_summary": agent.latest_change_summary
                    }
                }

        # 1. Get current month calls
        # 1. Get calls from the last 30 days (rolling window)
        now = datetime.now()
        start_date = now - timedelta(days=30)
        
        calls = db.query(Call).filter(
            Call.agent_id == agent.id,
            Call.call_timestamp >= start_date
        ).all()
        
        calls_count = len(calls)
        print(f"  - Found {calls_count} calls this month.")
        
        # Check if already updated recently (1 Hour Cache)
        # using dedicated column now


        if calls_count == 0:
            agent.latest_month_insight = "No calls recorded for this month."
            agent.latest_change_summary = "No activity to analyze."
            db.commit()
            return {
                "status": "success", 
                "message": "No calls found. Insights rolled over.",
                "data": {
                    "latest_month_insight": agent.latest_month_insight,
                    "overall_insight_text": agent.overall_insight_text
                }
            }

        # Prepare data for LLM
        calls_data = []
        for c in calls:
            # Safely access the relationship
            insight_obj = c.insight
            coaching = insight_obj.coaching_insight if insight_obj else "N/A"
            remarks = insight_obj.human_remarks if insight_obj else "N/A"
            
            calls_data.append({
                "date": c.call_timestamp.strftime("%Y-%m-%d"),
                "coaching_insight": coaching,
                "human_remarks": remarks
            })

        # Step 1: Generate Monthly Insight
        monthly_insight = generate_agent_monthly_insight(agent.name, calls_data)
        agent.latest_month_insight = monthly_insight
        
        # Step 2: Update Overall Level (Integrate)
        current_overall = agent.overall_insight_text
        updated_overall, change_summary = update_overall_insight(current_overall, monthly_insight)
        
        agent.overall_insight_text = updated_overall
        agent.latest_change_summary = change_summary
        agent.last_updated_at = datetime.now()
        agent.last_insight_generated_at = datetime.now()
        

        
        db.commit()
        print("  - Insights updated successfully.")
        
        return {
            "status": "success",
            "message": "Insights updated successfully.",
            "data": {
                "latest_month_insight": agent.latest_month_insight,
                "overall_insight_text": agent.overall_insight_text,
                "latest_change_summary": agent.latest_change_summary
            }
        }

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}