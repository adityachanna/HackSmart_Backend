# API Updates Summary - 2026-02-01

## ✅ Completed Updates

### 1. Call Ingestion Endpoint (`POST /ingest/call`)
**Status:** ✅ Already includes `customer_preferred_language`

**Accepted Parameters:**
- `file` (MP3) - required
- `agent_identifier` - required
- `issue_category` - required
- `city_identifier` - required
- `customer_name` - optional
- `customer_phone` - optional
- **`customer_preferred_language`** - optional ✅
- `call_context` - optional
- `agent_manual_note` - optional

---

### 2. Escalation Monitoring Routes - Enhanced

All three escalation routes now return:

#### **Added Fields:**
- ✅ `customer_preferred_language` - From Call table
- ✅ `sentiment_stabilization` - Score in the `scores` object
- ✅ `sentiment_trajectory` - Full JSONB array with turn-by-turn sentiment

#### **Affected Endpoints:**
1. `GET /api/escalations/monitor`
2. `GET /api/escalations/monitor/score?min_score=0.5`
3. `GET /api/agents/{agent_id}/worst-call`

#### **Response Example:**
```json
{
  "flagged_calls": [
    {
      "call_id": "uuid",
      "customer_preferred_language": "hindi",
      "scores": {
        "sentiment_stabilization": 0.49,
        "coaching_priority": 1.0,
        ...
      },
      "sentiment_trajectory": [
        {
          "turn": 2,
          "score": 0.3,
          "sentiment": "frustrated"
        },
        {
          "turn": 4,
          "score": 0.5,
          "sentiment": "neutral"
        }
      ],
      "sop_deviations": [...],
      "analysis": {...}
    }
  ]
}
```

---

### 3. Agent Details Route - Comprehensive Update

**Endpoint:** `GET /api/agents/{agent_id}/details`

#### **New Data Sections Added:**

**A. Enhanced Current Stats**
```json
"current_stats": {
  "quality_score": 0.95,
  "sop_compliance": 0.90,
  "sentiment_stabilization": 0.85,
  "escalation_rate": 0.05,
  "calls_handled_today": 12,
  "emergencies_today": 1,
  "calls_handled_total": 620,        // ✅ NEW
  "total_emergencies_count": 15      // ✅ NEW
}
```

**B. Previous Month Stats (Renamed & Expanded)**
```json
"previous_month_stats": {           // ✅ Renamed from "history_comparison"
  "quality_score": 0.88,
  "sop_compliance": 0.85,
  "sentiment_stabilization": 0.80,
  "escalation_rate": 0.08,
  "calls_handled": 580,              // ✅ NEW
  "emergencies": 12                  // ✅ NEW
}
```

**C. Insight Metadata (Completely New)**
```json
"insight_metadata": {                // ✅ NEW SECTION
  "insight_history": [               // Historical insights JSONB
    {"month": "2025-12", "insight": "..."}
  ],
  "recent_trend_array": [            // Recent trends JSONB
    {"metric": "quality", "trend": "up"}
  ],
  "last_insight_generated_at": "2026-01-31T15:30:00",
  "last_updated_at": "2026-02-01T03:00:00"
}
```

**D. Existing Sections (Unchanged)**
- `agent_profile` - ID, name, employee_id, languages
- `trend_data` - 4 metric trends (up/down/stable)
- `llm_insights` - Latest insights text

---

## 📊 Complete Agent Details Response Structure

```json
{
  "status": "success",
  "data": {
    "agent_profile": {
      "id": "uuid",
      "name": "John Doe",
      "employee_id": "EMP-001",
      "languages": ["English", "Hindi"]
    },
    "current_stats": {
      "quality_score": 0.95,
      "sop_compliance": 0.90,
      "sentiment_stabilization": 0.85,
      "escalation_rate": 0.05,
      "calls_handled_today": 12,
      "emergencies_today": 1,
      "calls_handled_total": 620,
      "total_emergencies_count": 15
    },
    "previous_month_stats": {
      "quality_score": 0.88,
      "sop_compliance": 0.85,
      "sentiment_stabilization": 0.80,
      "escalation_rate": 0.08,
      "calls_handled": 580,
      "emergencies": 12
    },
    "trend_data": [
      {
        "metric": "quality_score",
        "trend": "up",
        "value": 0.95,
        "prev_value": 0.88
      },
      {
        "metric": "sop_compliance",
        "trend": "up",
        "value": 0.90,
        "prev_value": 0.85
      },
      {
        "metric": "sentiment_stabilization",
        "trend": "up",
        "value": 0.85,
        "prev_value": 0.80
      },
      {
        "metric": "escalation_rate",
        "trend": "down",
        "value": 0.05,
        "prev_value": 0.08
      }
    ],
    "llm_insights": {
      "latest_month_insight": "Strong performance this month...",
      "overall_insight_text": "Consistently high performer...",
      "latest_change_summary": "7% improvement in SOP compliance..."
    },
    "insight_metadata": {
      "insight_history": [],
      "recent_trend_array": [],
      "last_insight_generated_at": "2026-01-31T15:30:00",
      "last_updated_at": "2026-02-01T03:00:00"
    }
  }
}
```

---

## 🎯 Summary of Changes

| Component | Fields Added | Status |
|-----------|--------------|--------|
| Call Ingestion | `customer_preferred_language` | ✅ Already present |
| Escalation Routes | `customer_preferred_language`, `sentiment_trajectory` | ✅ Added |
| Agent Details | `calls_handled_total`, `total_emergencies_count`, `previous_month_stats` (calls/emergencies), `insight_metadata` (4 fields) | ✅ Enhanced |

**Total New/Enhanced Fields:** 10+ fields

---

## 📌 Breaking Changes

⚠️ **Agent Details API Response Structure Changed:**
- `history_comparison` → `previous_month_stats` (renamed)
- `previous_month_stats` now includes `calls_handled` and `emergencies`
- New section `insight_metadata` added

**Migration Guide for Frontend:**
```javascript
// OLD
const prevQuality = response.data.history_comparison.prev_month_quality;

// NEW
const prevQuality = response.data.previous_month_stats.quality_score;
```

---

## ✅ All Updates Complete!
All routes now provide comprehensive data aligned with the database schema.
