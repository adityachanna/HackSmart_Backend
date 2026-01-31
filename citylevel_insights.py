
import os
import json
import requests
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import text
from connection import engine
from models import City, Call, CityInsight
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
MODEL_NAME = "x-ai/grok-4.1-fast"

def get_llm_response(prompt, system_prompt="You are a helpful analyst."):
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
        "max_tokens": 1200
    }

    try:
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()
        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content'].strip()
        return None
    except Exception as e:
        print(f"LLM Request Failed: {e}")
        return None

def generate_city_daily_ops_insight(city_name, daily_calls_data):
    """
    Generates daily operational insight for a city based on today's calls.
    Focuses on 'business_insight' column from calls.
    """
    if not daily_calls_data:
        return "No calls recorded today for operational analysis."

    # Summary of business insights
    summary_text = "\n".join([
        f"- Call: {c['business_insight']}" 
        for c in daily_calls_data[:50]
    ])

    prompt = f"""
    Analyze the following operational business insights from today's calls in {city_name}.
    
    Data:
    {summary_text}
    
    Task:
    Generate a 'Daily Ops Insight' (100 words or less).
    - Identify any immediate operational bottlenecks, surged issues, or patterns today.
    - Be specific.
    - Do NOT include word counts.
    - Do NOT use markdown formatting. Return plain text only.
    """
    return get_llm_response(prompt, system_prompt="You are a City Operations Manager.")

def generate_city_monthly_insight(city_name, month_calls_data):
    """
    Generates monthly insight based on 'business_insight' from calls in the last 30 days.
    """
    if not month_calls_data:
        return "No calls recorded in the last 30 days."

    summary_text = "\n".join([
        f"- {c['business_insight']}"
        for c in month_calls_data[:50] # Limit to last 50 calls
    ])

    prompt = f"""
    Analyze the business insights for {city_name} from the last 30 days.
    
    Data:
    {summary_text}
    
    Task:
    Generate a 'Latest Month Insight' (100 words or less).
    - Summarize key operational trends, recurring business problems, and volume drivers.
    - Highlight macro-level issues affecting the city.
    - Do NOT include word counts.
    - Do NOT use markdown formatting. Return plain text only.
    """
    return get_llm_response(prompt, system_prompt="You are a Regional Operations Director.")

def update_city_overall_insight(current_overall, monthly_insight):
    """
    Updates the overall city insight by integrating the new monthly insight.
    """
    if not current_overall:
        current_overall = "No previous history available."

    prompt = f"""
    You are maintaining the long-term operational profile of a city.
    
    Current Overall Insight:
    "{current_overall}"
    
    New Monthly Insight:
    "{monthly_insight}"
    
    Task:
    Create an UPDATED 'Overall City Insight' (100 words or less).
    - Merge new findings with historical context.
    - Reinforce persistent trends or note if long-standing issues are resolving.
    - Do NOT include word counts.
    - Do NOT use markdown formatting. Return plain text only.
    """
    return get_llm_response(prompt)

def generate_city_coaching_focus(city_name, month_calls_data):
    """
    Generates a city-wide coaching focus based on 'coaching_insight' from calls.
    """
    if not month_calls_data:
        return "No sufficient data for coaching analysis."

    # Filter for calls that actually have coaching insights
    coaching_extracts = [c['coaching_insight'] for c in month_calls_data if c.get('coaching_insight') and c.get('coaching_insight') != 'N/A']
    
    if not coaching_extracts:
        return "No coaching insights available to analyze."

    summary_text = "\n".join([f"- {txt}" for txt in coaching_extracts[:50]])

    prompt = f"""
    Analyze the individual coaching insights for agents in {city_name} over the last month.
    
    Coaching Logs:
    {summary_text}
    
    Task:
    Generate a 'Coaching Focus for City' (100 words or less).
    - Identify common skill gaps across agents in this city (e.g., empathy, process knowledge, closing).
    - Recommend specific training modules or focus areas for the city team.
    - Do NOT include word counts.
    - Do NOT use markdown formatting. Return plain text only.
    """
    return get_llm_response(prompt, system_prompt="You are a Training & Quality Lead.")

def update_single_city_insights(db: Session, city_id: int):
    """
    Main function to generate/update all city-level insights.
    """
    try:
        city = db.query(City).filter(City.id == city_id).first()
        if not city:
            return {"status": "error", "message": f"City {city_id} not found."}
        
        print(f"Generating insights for City: {city.name}...")

        # Time windows
        now = datetime.now()

        # ---------------------------------------------------------
        # OPTIMIZATION: Check Cache BEFORE fetching expensive data
        # ---------------------------------------------------------
        # Ensure CityInsight record exists
        city_insight_record = db.query(CityInsight).filter(CityInsight.city_id == city.id).first()
        if not city_insight_record:
            city_insight_record = CityInsight(city_id=city.id)
            db.add(city_insight_record)
            db.flush()
        else:
            # OPTIMIZATION: Cache Strategy
            # 1. Valid for 1 hour by default
            # 2. BUT if calls arrived in last 10 mins, force refresh (for Daily Ops)
            
            # Check for recent calls (last 10 mins)
            ten_mins_ago = now - timedelta(minutes=10)
            
            recent_calls_exist = db.query(Call).filter(
                Call.city_id == city.id,
                Call.call_timestamp >= ten_mins_ago
            ).first()
            
            cache_valid_duration = timedelta(hours=1)
            is_cache_fresh = False
            
            # Use specific insight timestamp
            if city_insight_record.last_insight_generated_at:
                if (now - city_insight_record.last_insight_generated_at) < cache_valid_duration:
                    is_cache_fresh = True
            
            # If cache is fresh AND no urgent new data -> Return Cached
            if is_cache_fresh and not recent_calls_exist:
                print("  - Insights cached (<1hr) and no recent calls (10m). Returning cached values.")
                return {
                    "status": "success",
                    "message": f"Insights retrieved from cache for {city.name}",
                    "data": {
                        "daily_ops_insight": city_insight_record.daily_ops_insight,
                        "latest_month_insight": city_insight_record.latest_month_insight,
                        "overall_city_insight": city_insight_record.overall_city_insight,
                        "coaching_focus_for_city": city_insight_record.coaching_focus_for_city
                    }
                }
            
            if recent_calls_exist:
                print("  ! Recent calls detected (10m). Forcing Insight Refresh.")
        start_of_30_days = now - timedelta(days=30)
        start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)

        # 1. Fetch Calls (Last 30 Days)
        # We need to join with CallInsight to get business_insight and coaching_insight
        # Note: In models.py, Call has 'insight' relationship to CallInsight
        calls_month = db.query(Call).filter(
            Call.city_id == city.id,
            Call.call_timestamp >= start_of_30_days
        ).order_by(Call.call_timestamp.desc()).all()
        
        # Prepare data structures
        month_business_data = []
        month_coaching_data = []
        today_business_data = []

        for call in calls_month:
            insight_obj = call.insight
            business_txt = insight_obj.business_insight if insight_obj else "N/A"
            coaching_txt = insight_obj.coaching_insight if insight_obj else "N/A"
            
            item = {
                "date": call.call_timestamp,
                "business_insight": business_txt,
                "coaching_insight": coaching_txt
            }
            
            # Add to monthly lists
            month_business_data.append(item)
            month_coaching_data.append(item)

            # Check if today
            # Handle potential timezone mismatch (offset-naive vs offset-aware)
            c_ts = call.call_timestamp
            if c_ts is not None:
                if c_ts.tzinfo is not None:
                     # If DB timestamp is aware, strip it for comparison with naive local time
                     c_ts = c_ts.replace(tzinfo=None)
                
                if c_ts >= start_of_today:  
                    today_business_data.append(item)

        # Ensure CityInsight record exists
        city_insight_record = db.query(CityInsight).filter(CityInsight.city_id == city.id).first()
        if not city_insight_record:
            city_insight_record = CityInsight(city_id=city.id)
            db.add(city_insight_record)
            db.flush()
        else:
            # OPTIMIZATION: Cache Strategy
            # 1. Valid for 1 hour by default
            # 2. BUT if calls arrived in last 10 mins, force refresh (for Daily Ops)
            
            # Check for recent calls (last 10 mins)
            ten_mins_ago = now - timedelta(minutes=10)
            # Normalize for timezone safety if needed (assuming now is local/naive like before fix in line 212)
            # Actually line 212 fix handles call.call_timestamp being aware. We need a query here.
            
            recent_calls_exist = db.query(Call).filter(
                Call.city_id == city.id,
                Call.call_timestamp >= ten_mins_ago
            ).first()
            
            cache_valid_duration = timedelta(hours=1)
            is_cache_fresh = False
            
            if city_insight_record.last_insight_generated_at:
                if (now - city_insight_record.last_insight_generated_at) < cache_valid_duration:
                    is_cache_fresh = True

            # If cache is fresh AND no urgent new data -> Return Cached
            if is_cache_fresh and not recent_calls_exist:
                print("  - Insights cached (<1hr) and no recent calls (10m). Returning cached values.")
                return {
                    "status": "success",
                    "message": f"Insights retrieved from cache for {city.name}",
                    "data": {
                        "daily_ops_insight": city_insight_record.daily_ops_insight,
                        "latest_month_insight": city_insight_record.latest_month_insight,
                        "overall_city_insight": city_insight_record.overall_city_insight,
                        "coaching_focus_for_city": city_insight_record.coaching_focus_for_city
                    }
                }
            
            if recent_calls_exist:
                print("  ! Recent calls detected (10m). Forcing Insight Refresh.")
    
        # --- A. Daily Ops Insight ---
        print("  - Generating Daily Ops Insight...")
        daily_ops = generate_city_daily_ops_insight(city.name, today_business_data)
        city_insight_record.daily_ops_insight = daily_ops

        # --- B. Monthly Insight (Business) ---
        print("  - Generating Monthly Insight...")
        monthly_insight = generate_city_monthly_insight(city.name, month_business_data)
        city_insight_record.latest_month_insight = monthly_insight

        # --- C. Overall City Insight (Update) ---
        print("  - Updating Overall Insight...")
        current_overall = city_insight_record.overall_city_insight
        updated_overall = update_city_overall_insight(current_overall, monthly_insight)
        city_insight_record.overall_city_insight = updated_overall

        # --- D. Coaching Focus (City Wide) ---
        # Logic: Only generate if it's a new month compared to the last update, or if it's currently empty.
        should_generate_coaching = True
        if city_insight_record.coaching_focus_for_city and city_insight_record.last_insight_generated_at:
            if city_insight_record.last_insight_generated_at.month == now.month and city_insight_record.last_insight_generated_at.year == now.year:
                should_generate_coaching = False
                print("  - Skipping Coaching Focus (already generated this month).")

        coaching_focus = city_insight_record.coaching_focus_for_city # Default to existing
        
        if should_generate_coaching:
            print("  - Generating Coaching Focus...x")
            coaching_focus = generate_city_coaching_focus(city.name, month_coaching_data)
            city_insight_record.coaching_focus_for_city = coaching_focus
        else:
            # Keep existing value
            pass
        
        # Update timestamp
        city_insight_record.last_updated_at = datetime.now()
        city_insight_record.last_insight_generated_at = datetime.now()
        
        db.commit()
        print(f"✓ Insights updated for {city.name}")

        return {
            "status": "success",
            "message": f"Insights updated for {city.name}",
            "data": {
                "daily_ops_insight": daily_ops,
                "latest_month_insight": monthly_insight,
                "overall_city_insight": updated_overall,
                "coaching_focus_for_city": coaching_focus
            }
        }

    except Exception as e:
        db.rollback()
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": str(e)}
