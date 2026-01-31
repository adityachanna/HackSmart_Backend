import os
import random
import uuid
import boto3
import base64
import tempfile
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import text
from dotenv import load_dotenv
from connection import engine
load_dotenv()
# AWS S3 Configuration
S3_BUCKET_NAME = os.getenv("S3_BUCKET_NAME", "hacksmart-calls-bucket")
AWS_REGION = os.getenv("AWS_REGION", "us-west-2")

# Initialize S3 client (will use environment variables for credentials)
try:
    s3_client = boto3.client('s3', region_name=AWS_REGION)
except Exception as e:
    print(f"Warning: S3 client initialization failed: {e}")
    s3_client = None

# =====================================================
# CITIES WE SERVE (ID, NAME, STATE)
# =====================================================
CITIES_MAP = {
    1: {"name": "New Delhi", "state": "Delhi"},
    2: {"name": "Gurugram", "state": "Haryana"},
    3: {"name": "Bengaluru", "state": "Karnataka"},
    4: {"name": "Lucknow", "state": "Uttar Pradesh"},
    5: {"name": "Jaipur", "state": "Rajasthan"},
    6: {"name": "Hyderabad", "state": "Telangana"}
}

# =====================================================
# KNOWN AGENTS (FROM YOUR PROVIDED LIST)
# =====================================================
KNOWN_AGENTS = {
    "Khushboo 1": "6f8e4d3a-1b2c-4e5f-8a9d-123456789001",
    "Aniket Solanki": "6f8e4d3a-1b2c-4e5f-8a9d-123456789002",
    "Prakhar Pandey": "6f8e4d3a-1b2c-4e5f-8a9d-123456789003",
    "Prateeksha": "6f8e4d3a-1b2c-4e5f-8a9d-123456789004",
    "Jyoti Rani": "6f8e4d3a-1b2c-4e5f-8a9d-123456789005",
    "Kumkum Sisodiya": "6f8e4d3a-1b2c-4e5f-8a9d-123456789006",
    "Vikas": "6f8e4d3a-1b2c-4e5f-8a9d-123456789007",
    "Rocky Pandey": "6f8e4d3a-1b2c-4e5f-8a9d-123456789008",
    "Varsha Swain": "6f8e4d3a-1b2c-4e5f-8a9d-123456789009",
    "Deepa Upadhyay": "6f8e4d3a-1b2c-4e5f-8a9d-123456789010"
}

# =====================================================
# RANDOM DATA GENERATORS FOR OPTIONAL FIELDS
# =====================================================
RANDOM_CUSTOMER_NAMES = [
    "Amit Sharma", "Priya Singh", "Rahul Verma", "Sneha Gupta", 
    "Vikram Rao", "Anjali Nair", "Rohan Das", "Kavita Patel",
    "Arjun Mehta", "Pooja Reddy"
]

RANDOM_PHONES = [
    "9871234560", "9988776655", "8123456789", "9876543210",
    "8765432109", "9012345678", "7890123456"
]

CALL_CONTEXTS = [
    'NEW_ISSUE', 'FOLLOW_UP', 'ONGOING_CASE', 
    'REOPENED', 'INFORMATION_ONLY', 'CLOSED_ISSUE'
]

ISSUE_CATEGORIES = [
    "Login Issue", "Payment Problem", "Service Complaint",
    "Billing Query", "Technical Support", "Emergency Service",
    "Product Inquiry", "Account Update", "Feedback"
]

# =====================================================
# HELPER FUNCTIONS
# =====================================================

def ensure_cities(session):
    """Ensures all 6 cities exist in the database."""
    print("✓ Verifying cities in database...")
    for city_id, info in CITIES_MAP.items():
        query = text("SELECT id FROM cities WHERE id = :id")
        result = session.execute(query, {"id": city_id}).fetchone()
        
        if not result:
            print(f"  → Creating city: {info['name']}, {info['state']}")
            insert_sql = text("INSERT INTO cities (id, name, state) VALUES (:id, :name, :state)")
            try:
                session.execute(insert_sql, {
                    "id": city_id, 
                    "name": info['name'], 
                    "state": info['state']
                })
            except Exception as e:
                print(f"  ✗ Failed to insert city {info['name']}: {e}")
    session.commit()
    print("✓ Cities verified\n")


def validate_and_get_agent_id(session, agent_identifier):
    """
    Validates agent and returns UUID.
    
    Args:
        agent_identifier: Can be agent name, employee_id, or UUID string
    
    Returns:
        UUID of agent
    
    Raises:
        ValueError if agent not found
    """
    # Check if it's in our known agents list first
    if agent_identifier in KNOWN_AGENTS:
        agent_uuid = KNOWN_AGENTS[agent_identifier]
        print(f"✓ Found agent '{agent_identifier}' in known list (ID: {agent_uuid})")
        return agent_uuid
    
    # Try to find by name in database
    query = text("SELECT id FROM agents WHERE name = :name")
    result = session.execute(query, {"name": agent_identifier}).fetchone()
    
    if result:
        print(f"✓ Found agent '{agent_identifier}' in database (ID: {result[0]})")
        return str(result[0])
    
    # Try to find by employee_id
    query = text("SELECT id FROM agents WHERE employee_id = :emp_id")
    result = session.execute(query, {"emp_id": agent_identifier}).fetchone()
    
    if result:
        print(f"✓ Found agent by employee_id '{agent_identifier}' (ID: {result[0]})")
        return str(result[0])
    
    # Try as UUID directly
    try:
        agent_uuid = str(uuid.UUID(agent_identifier))
        query = text("SELECT id FROM agents WHERE id = :id")
        result = session.execute(query, {"id": agent_uuid}).fetchone()
        if result:
            print(f"✓ Found agent by UUID {agent_uuid}")
            return agent_uuid
    except (ValueError, AttributeError):
        pass
    
    raise ValueError(f"Agent '{agent_identifier}' not found in database. Available agents: {', '.join(KNOWN_AGENTS.keys())}")


def resolve_city_id(city_identifier):
    """
    Resolves city to city_id.
    
    Args:
        city_identifier: Can be city name or city ID (1-6)
    
    Returns:
        city_id (int)
    """
    # Try as integer ID
    try:
        city_id = int(city_identifier)
        if city_id in CITIES_MAP:
            print(f"✓ Resolved city ID: {city_id} ({CITIES_MAP[city_id]['name']})")
            return city_id
    except (ValueError, TypeError):
        pass
    
    # Try as city name
    city_lower = str(city_identifier).lower()
    for cid, info in CITIES_MAP.items():
        if info['name'].lower() == city_lower:
            print(f"✓ Resolved city '{city_identifier}' to ID: {cid}")
            return cid
    
    # Fallback to random city
    city_id = random.choice(list(CITIES_MAP.keys()))
    print(f"⚠ City '{city_identifier}' not found. Using random city: {CITIES_MAP[city_id]['name']} (ID: {city_id})")
    return city_id


def upload_to_s3(file_path=None, mp3_base64=None, filename_hint="recording.mp3"):
    """
    Uploads MP3 file to S3 and returns public URL.
    
    Args:
        file_path: Local path to audio file (optional)
        mp3_base64: Base64-encoded MP3 data (optional)
        filename_hint: Suggested filename for base64 uploads
    
    Returns:
        S3 URL string
    
    Note: Either file_path OR mp3_base64 must be provided
    """
    temp_file_path = None
    
    try:
        # Handle base64 input
        if mp3_base64:
            print(f"⬇ Decoding base64 MP3 data ({len(mp3_base64)} chars)...")
            try:
                # Decode base64 to bytes
                mp3_bytes = base64.b64decode(mp3_base64)
                
                # Create temporary file
                with tempfile.NamedTemporaryFile(mode='wb', suffix='.mp3', delete=False) as temp_file:
                    temp_file.write(mp3_bytes)
                    temp_file_path = temp_file.name
                
                print(f"✓ Decoded {len(mp3_bytes)} bytes to temporary file")
                file_path = temp_file_path
                
            except Exception as e:
                print(f"✗ Base64 decode error: {e}")
                return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/calls/decode_failed_{uuid.uuid4()}.mp3"
        
        # Check if file exists
        if not file_path or not os.path.exists(file_path):
            print(f"⚠ Warning: File '{file_path}' not found. Using dummy URL.")
            return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/calls/dummy_{uuid.uuid4()}.mp3"
        
        if not s3_client:
            print(f"⚠ Warning: S3 client not configured. Using dummy URL.")
            return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/calls/dummy_{uuid.uuid4()}.mp3"
        
        # Generate unique filename
        original_name = filename_hint if mp3_base64 else os.path.basename(file_path)
        file_name = f"calls/{datetime.now().strftime('%Y%m%d')}_{uuid.uuid4()}_{original_name}"
        
        print(f"⬆ Uploading to S3: {original_name}...")
        s3_client.upload_file(
            file_path, 
            S3_BUCKET_NAME, 
            file_name,
            ExtraArgs={'ContentType': 'audio/mpeg'}
        )
        
        # KEY FIX: Use the explicit regional endpoint as requested by S3
        # Format: https://<bucket>.s3-<region>.amazonaws.com/<key> (Dash before region)
        # OR: https://<bucket>.s3.<region>.amazonaws.com/<key> (Dot before region)
        # The error suggests: hacksmart-calls-bucket.s3-us-west-2.amazonaws.com
        
        url = f"https://{S3_BUCKET_NAME}.s3-{AWS_REGION}.amazonaws.com/{file_name}"
        print(f"✓ Upload successful: {url}")
        return url
        
    except Exception as e:
        print(f"✗ S3 Upload Error: {e}")
        return f"https://{S3_BUCKET_NAME}.s3.{AWS_REGION}.amazonaws.com/calls/upload_failed_{uuid.uuid4()}.mp3"
    
    finally:
        # Clean up temporary file if created
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.unlink(temp_file_path)
                print(f"🗑 Cleaned up temporary file")
            except Exception as e:
                print(f"⚠ Failed to clean up temp file: {e}")


# =====================================================
# MAIN INGESTION FUNCTION
# =====================================================

def ingest_call(
    agent_identifier,
    issue_category,
    city_identifier,
    mp3_path=None,
    mp3_base64=None,
    customer_name=None,
    customer_phone=None,
    call_context=None,
    duration_seconds=None,
    agent_manual_note=None
):
    """
    Complete call ingestion function.
    
    MANDATORY PARAMETERS:
    - agent_identifier: Agent name, employee_id, or UUID (str)
    - issue_category: Primary issue category (str)
    - city_identifier: City name or ID (str/int)
    - mp3_path OR mp3_base64: Either file path (str) OR base64-encoded MP3 data (str)
    
    OPTIONAL PARAMETERS (will be generated randomly if not provided):
    - customer_name: Customer name (str)
    - customer_phone: Customer phone number (str)
    - call_context: One of CALL_CONTEXTS (str)
    - duration_seconds: Call duration in seconds (int)
    - agent_manual_note: Agent's manual notes (str)
    
    RETURNS:
    - call_id (UUID): The created call's UUID
    """
    
    print("\n" + "="*60)
    print("CALL INGESTION STARTED")
    print("="*60 + "\n")
    
    # Validate mandatory parameters
    if not mp3_path and not mp3_base64:
        raise ValueError("Either mp3_path or mp3_base64 must be provided")
    if mp3_path and mp3_base64:
        raise ValueError("Provide either mp3_path OR mp3_base64, not both")
    if not agent_identifier:
        raise ValueError("agent_identifier is mandatory")
    if not issue_category:
        raise ValueError("issue_category is mandatory")
    if not city_identifier:
        raise ValueError("city_identifier is mandatory")
    
    session = Session(engine)
    
    try:
        # 1. Ensure cities exist
        ensure_cities(session)
        
        # 2. Validate and resolve agent
        print(f"→ Validating agent: '{agent_identifier}'")
        agent_id = validate_and_get_agent_id(session, agent_identifier)
        
        # 3. Resolve city
        print(f"→ Resolving city: '{city_identifier}'")
        city_id = resolve_city_id(city_identifier)
        
        # 4. Upload to S3
        if mp3_base64:
            print(f"→ Processing base64 MP3 data...")
            audio_url = upload_to_s3(mp3_base64=mp3_base64, filename_hint=f"call_{uuid.uuid4()}.mp3")
        else:
            print(f"→ Processing audio file: '{mp3_path}'")
            audio_url = upload_to_s3(file_path=mp3_path)
        
        # 5. Fill optional fields with random data if not provided
        customer_name = customer_name or random.choice(RANDOM_CUSTOMER_NAMES)
        customer_phone = customer_phone or random.choice(RANDOM_PHONES)
        
        # Enforce +91 prefix
        customer_phone = str(customer_phone).strip()
        if not customer_phone.startswith("+91"):
            customer_phone = f"+91{customer_phone}"
            
        call_context = call_context or random.choice(CALL_CONTEXTS)
        duration_seconds = duration_seconds or random.randint(60, 600)
        
        print(f"\n→ Call Details:")
        print(f"  • Agent: {agent_identifier} ({agent_id})")
        print(f"  • City: {CITIES_MAP[city_id]['name']} (ID: {city_id})")
        print(f"  • Issue: {issue_category}")
        print(f"  • Customer: {customer_name} ({customer_phone})")
        print(f"  • Context: {call_context}")
        print(f"  • Duration: {duration_seconds}s")
        
        # 6. Insert call into database
        new_call_id = uuid.uuid4()
        
        insert_call_sql = text("""
            INSERT INTO calls (
                id, agent_id, city_id, customer_phone, customer_name,
                audio_url, duration_seconds, call_timestamp, call_context, 
                primary_issue_category, agent_manual_note, processing_status
            ) VALUES (
                :id, :agent_id, :city_id, :phone, :name,
                :url, :duration, :timestamp, :context, 
                :issue, :note, 'pending'
            )
        """)
        
        session.execute(insert_call_sql, {
            "id": str(new_call_id),
            "agent_id": agent_id,
            "city_id": city_id,
            "phone": customer_phone,
            "name": customer_name,
            "url": audio_url,
            "duration": duration_seconds,
            "timestamp": datetime.now(),
            "context": call_context,
            "issue": issue_category,
            "note": agent_manual_note
        })
        
        session.commit()
        
        print(f"\n{'='*60}")
        print(f"✓ CALL SUCCESSFULLY INGESTED")
        print(f"  Call ID: {new_call_id}")
        print(f"{'='*60}\n")
        
        return str(new_call_id)
    
    except Exception as e:
        session.rollback()
        print(f"\n✗ INGESTION FAILED: {e}\n")
        raise e
    
    finally:
        session.close()

# =====================================================
# CLI INTERFACE
# =====================================================

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ingest call recordings into the database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
Examples:
  # Using MP3 file path
  python call_engestion.py --mp3 recording.mp3 --agent "Khushboo 1" --issue "Login Issue" --city "New Delhi"
  
  # Using base64-encoded MP3
  python call_engestion.py --mp3-base64 "UklGRiQAAABXQVZF..." --agent "Vikas" --issue "Emergency" --city 1
  
  # With employee ID
  python call_engestion.py --mp3 call.mp3 --agent "BS-EMP-002" --issue "Payment Problem" --city 3

Available Agents: {', '.join(KNOWN_AGENTS.keys())}
Available Cities: {', '.join([f"{cid}={info['name']}" for cid, info in CITIES_MAP.items()])}
        """
    )
    
    # Mandatory arguments
    parser.add_argument("--agent", required=True, help="Agent name, employee_id, or UUID")
    parser.add_argument("--issue", required=True, help="Primary issue category")
    parser.add_argument("--city", required=True, help="City name or ID (1-6)")
    
    # Audio input (one required)
    audio_group = parser.add_mutually_exclusive_group(required=True)
    audio_group.add_argument("--mp3", help="Path to MP3 audio file")
    audio_group.add_argument("--mp3-base64", help="Base64-encoded MP3 data")
    
    # Optional arguments
    parser.add_argument("--customer-name", help="Customer name (random if not provided)")
    parser.add_argument("--customer-phone", help="Customer phone (random if not provided)")
    parser.add_argument("--context", choices=CALL_CONTEXTS, help="Call context")
    parser.add_argument("--duration", type=int, help="Duration in seconds")
    parser.add_argument("--note", help="Agent's manual note")
    
    args = parser.parse_args()
    
    ingest_call(
        agent_identifier=args.agent,
        issue_category=args.issue,
        city_identifier=args.city,
        mp3_path=args.mp3,
        mp3_base64=args.mp3_base64,
        customer_name=args.customer_name,
        customer_phone=args.customer_phone,
        call_context=args.context,
        duration_seconds=args.duration,
        agent_manual_note=args.note
    )
