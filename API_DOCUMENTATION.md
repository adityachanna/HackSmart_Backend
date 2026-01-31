# HackSmart API Documentation

## Base URL
`http://localhost:8080`

---

## 📋 Configuration Endpoints

### 1. Get All Agents
```http
GET /config/agents
```
Returns list of all agents with their IDs and names.

### 2. Get All Cities
```http
GET /config/cities
```
Returns list of all cities with IDs, names, and states.

### 3. Get Issue Categories
```http
GET /config/issue-categories
```
Returns valid issue categories for classification.

### 4. Get Call Contexts
```http
GET /config/call-contexts
```
Returns valid call context types.

---

## 📞 Call Ingestion & Processing

### 5. Ingest Call
```http
POST /ingest/call
Content-Type: multipart/form-data
```

**Form Data:**
- `file` (required): MP3 audio file
- `agent_identifier` (required): Agent name, employee ID, or UUID
- `issue_category` (required): Primary issue category
- `city_identifier` (required): City name or ID (1-6)
- `customer_name` (optional): Customer name
- `customer_phone` (optional): Customer phone
- `customer_preferred_language` (optional): Language preference
- `call_context` (optional): Call context type
- `agent_manual_note` (optional): Agent's notes

**Response:**
```json
{
  "status": "success",
  "message": "Call ingested successfully and queued for processing",
  "call_id": "uuid",
  "media_info": {
    "filename": "call.mp3",
    "duration_seconds": 120
  }
}
```

### 6. Process Call for AI Evaluation
```http
POST /api/calls/{call_id}/process
```
Manually trigger AI processing for a call.

### 7. Get Call Processing Status
```http
GET /api/calls/{call_id}/status
```

**Response:**
```json
{
  "status": "success",
  "call_id": "uuid",
  "processing_status": "analyzed",
  "audio_url": "https://s3..."
}
```

---

## 📊 Dashboard & Analytics

### 8. India Risk Map Dashboard
```http
GET /api/dashboard/india-map
```

**Response:**
```json
{
  "status": "success",
  "data": [
    {
      "state": "Delhi",
      "risk_level": "high",
      "avg_sop_score": 0.65,
      "total_calls": 150,
      "cities": [...]
    }
  ]
}
```

### 9. Agent Leaderboard
```http
GET /api/leaderboard
```

**Response:**
```json
{
  "status": "success",
  "leaderboard": [
    {
      "rank": 1,
      "agent_id": "uuid",
      "name": "John Doe",
      "quality_score": 0.95,
      "trend_data": [...]
    }
  ]
}
```

### 10. Search Agents
```http
GET /api/agents/search?query=john
```

### 11. Get Agent Details
```http
GET /api/agents/{agent_id}/details
```

**Response:**
```json
{
  "status": "success",
  "agent": {
    "id": "uuid",
    "name": "John Doe",
    "employee_id": "EMP-001",
    "current_stats": {
      "quality_score": 0.95,
      "sop_compliance": 0.90,
      ...
    },
    "insights": {
      "latest_month_insight": "...",
      "overall_insight_text": "...",
      "latest_change_summary": "..."
    }
  }
}
```

### 12. Get Cities List
```http
GET /api/cities
```

### 13. Get City Details
```http
GET /api/cities/{city_id}/details
```

**Response:**
```json
{
  "status": "success",
  "city": {
    "id": 1,
    "name": "New Delhi",
    "state": "Delhi",
    "metrics": {
      "avg_quality_score": 0.85,
      "total_calls": 500
    },
    "insights": {
      "daily_ops_insight": "...",
      "overall_city_insight": "..."
    }
  }
}
```

---

## 🧠 Insights Generation

### 14. Generate Agent Insights
```http
POST /api/agents/{agent_id}/insights
```
Triggers LLM-based insight generation for an agent (cached for 1 hour).

### 15. Generate City Insights
```http
POST /api/cities/{city_id}/insights
```
Triggers LLM-based insight generation for a city (cached for 1 hour, refreshed if new calls in last 10 mins).

---

## 🚨 Escalation Monitoring

### 16. Monitor Escalatory Calls (Real-time)
```http
GET /api/escalations/monitor
```

**Response:**
```json
{
  "status": "success",
  "timestamp": "2026-02-01T03:36:00",
  "time_window": "last_5_minutes",
  "count": 2,
  "flagged_calls": [
    {
      "call_id": "uuid",
      "audio_url": "https://...",
      "agent": {...},
      "scores": {
        "coaching_priority": 0.95
      },
      "sop_deviations": [
        {
          "turn_number": 11,
          "start_time": 54.06,
          "deviated_phrase": "...",
          "what_was_wrong": "privacy_violation",
          "severity": 0.9
        }
      ],
      "sentiment_trajectory": [...],
      "analysis": {...}
    }
  ]
}
```

**Polling Recommendation:** Every 5-10 seconds for supervisor alerts

### 17. Monitor Escalatory Calls (Score-based)
```http
GET /api/escalations/monitor/score?min_score=0.5
```

**Query Parameters:**
- `min_score` (default: 0.5): Minimum coaching priority to flag (0-1)

Same response format as endpoint 16.

### 18. Get Agent's Worst Call (Past Week)
```http
GET /api/agents/{agent_id}/worst-call
```

**Response:**
```json
{
  "status": "success",
  "timestamp": "2026-02-01T03:38:00",
  "time_window": "last_7_days",
  "agent_id": "uuid",
  "worst_call": {
    "call_id": "uuid",
    "call_timestamp": "2026-01-28T10:30:00",
    "audio_url": "https://...",
    "scores": {
      "coaching_priority": 1.0,
      "sop_compliance": 0.0
    },
    "sop_deviations": [...],
    "analysis": {...}
  }
}
```

---

## 🏥 Health Check

### 19. Health Check
```http
GET /health
```

### 20. Database Connection Check
```http
GET /db/check
```

---

## 📊 Data Models Reference

### Call Processing Status Values
- `pending`: Call uploaded, awaiting AI processing
- `transcribed`: Audio transcribed
- `analyzed`: Full AI analysis complete
- `failed`: Processing error

### Call Context Values
- `NEW_ISSUE`
- `FOLLOW_UP`
- `ONGOING_CASE`
- `REOPENED`
- `INFORMATION_ONLY`
- `CLOSED_ISSUE`

### Risk Levels (Dashboard)
- `high`: SOP score < 0.6
- `medium`: SOP score 0.6-0.8
- `low`: SOP score > 0.8

---

## 🔄 Integration Flow

1. **Call Ingestion**: `POST /ingest/call` → Uploads MP3 to S3 → Creates Call record
2. **Auto Processing**: Backend automatically calls AI agent API
3. **Analysis Storage**: Results saved to `call_insights` table with JSONB fields
4. **Real-time Monitoring**: Frontend polls `/api/escalations/monitor` every 10s
5. **Insight Generation**: On-demand via `/api/agents/{id}/insights` (cached 1hr)

---

## 🎯 Frontend Recommendations

### Dashboard Polling
```javascript
// Update dashboard every 30 seconds
setInterval(() => {
  fetch('/api/dashboard/india-map').then(r => r.json()).then(updateMap);
}, 30000);
```

### Escalation Alerts
```javascript
// Poll for escalations every 10 seconds
setInterval(async () => {
  const res = await fetch('/api/escalations/monitor/score?min_score=0.7');
  const data = await res.json();
  if (data.count > 0) showAlert(data.flagged_calls);
}, 10000);
```

---

## 📝 Notes

- All timestamps are in ISO 8601 format
- All UUIDs are RFC 4122 compliant
- Audio files must be MP3 format
- Scores are normalized 0-1 (except sentiment which uses 0, 0.5, 1)
- JSONB fields contain structured analysis data from AI agent
