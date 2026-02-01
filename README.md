# HackSmart Backend — In-Depth Guide

Welcome to the HackSmart Backend repository. This README is an extended, in-depth companion to the included API documentation and schema files. It explains architecture, data model, developer workflows, deployment options, internals of the ingestion & AI pipeline, operational guidance, debugging tips, and recommended improvements.

Contents
- Project overview
- High-level architecture and data flow
- Detailed API reference (key endpoints with examples)
- Database schema and models (field-by-field)
- Call ingestion lifecycle (step-by-step)
- AI processing pipeline (transcription → scoring → insights)
- Storage, secrets, and environment variables
- Running locally, tests, and debugging
- Deployment, scaling, monitoring & observability
- Operational playbook and troubleshooting
- Security considerations
- Contributing, roadmap, and contacts

---

Project summary
- Purpose: Ingest customer support call audio, transcribe, evaluate agent SOP compliance and other quality signals via AI, store results, and provide dashboards & alerts to improve agent performance and surface risk.
- Built with: FastAPI, SQLAlchemy, PostgreSQL (Supabase-compatible schema), LangChain/OpenAI for LLM evaluation, AWS S3 for audio storage, and standard Python tooling.
- Repo entrypoints & notable files:
  - backend.py — FastAPI application and routes
  - call_engestion.py — audio ingestion & storage logic
  - call_processing_service.py — orchestration of AI evaluation for a call
  - ingestion/analysis helpers: insights.py, citylevel_insights.py, escalation_monitor.py
  - dashboard & leaderboard services: dashboard_service.py, leaderboard_service.py, city_service.py
  - models.py — database models (SQLAlchemy)
  - connection.py — SQLAlchemy engine/session
  - schema.md — authoritative Postgres DDL

---

High-level architecture and data flow
1. Frontend or ingestion client uploads an MP3 + metadata to `POST /ingest/call`.
2. Backend validates input, stores the audio file to S3 (or a configured object store), records metadata in `calls` table with `processing_status='pending'`.
3. A separate worker or on-demand process (call_processing_service.py) picks the call:
   - Downloads audio from S3
   - Transcribes audio (speech-to-text)
   - Runs scoring & LLM evaluations (SOP compliance, sentiment, escalation)
   - Writes results to `call_insights` and updates `calls.processing_status` to `transcribed` / `analyzed` or `failed`
4. Aggregation services (leaderboard_service, dashboard_service) query agent/call data to produce dashboards and risk maps.
5. Escalation monitor periodically queries call_insights to find high-risk calls and emits alerts or returns them via API.

Notes:
- The API exposes endpoints to manually trigger processing, check status, and retrieve aggregated dashboards.
- The system stores agent-level trend/history JSONB arrays to produce insights and enable LLM memory for monthly summaries and recommended coaching actions.

---

Detailed API reference (selected endpoints)
This README expands the documentation in API_DOCUMENTATION.md with precise examples, edge cases, required fields, validation, and expected errors.

Base URL (local dev)
- http://localhost:8080

1) POST /ingest/call — Ingest an audio call
- Content-Type: multipart/form-data
- Form fields:
  - file (required) — mp3 audio binary
  - agent_identifier (required) — agent UUID, employee ID or name
  - issue_category (required) — primary issue classification
  - city_identifier (required) — city name or id
  - customer_name (optional)
  - customer_phone (optional)
  - customer_preferred_language (optional) — e.g., "Hindi", "English"
  - call_context (optional) — one of NEW_ISSUE, FOLLOW_UP, ONGOING_CASE, REOPENED, INFORMATION_ONLY, CLOSED_ISSUE
  - agent_manual_note (optional)
- Typical flow:
  - Store incoming file to a temporary path
  - Validate MP3 (mutagen used in code to read duration: mutagen.mp3.MP3)
  - Upload to S3 and create a `calls` row
- Successful response (201):
  {
    "status": "success",
    "message": "Call ingested successfully and queued for processing",
    "call_id": "<uuid>",
    "media_info": {"filename":"call.mp3","duration_seconds":120}
  }
- Errors:
  - 400 for missing required fields or invalid audio
  - 500 for storage/database failures

Example curl:
curl -X POST "http://localhost:8080/ingest/call" \
  -F "file=@/path/to/call.mp3" \
  -F "agent_identifier=EMP-123" \
  -F "issue_category=Battery Pick-Up Request" \
  -F "city_identifier=New Delhi"

2) POST /api/calls/{call_id}/process — Trigger processing
- Use for on-demand processing if asynchronous worker is not set up.
- Returns job status or immediate analysis result if processing is synchronous.

3) GET /api/calls/{call_id}/status — Check processing status
- Returns JSON:
  {
    "status": "success",
    "call_id": "...",
    "processing_status": "analyzed",
    "audio_url": "https://s3.../call.mp3"
  }

4) GET /api/dashboard/india-map — Aggregated dashboard per state
- Returns array of states with metrics:
  - state, overall_sop_score, total_call_volume_pct, top_issue, cities[] (id, name, sop_score)
- Useful for map visualizations.

5) GET /api/agents/leaderboard — Agent leaderboard
- Returns list of agents ranked by quality score:
  - rank, agent_id, name, overall_score, calls_received, emergencies

6) GET /api/agents/search?query=... — Search agents by name/ID

7) GET /api/agents/{agent_id}/details — Full agent details & recent insights

8) GET /api/escalations/... — Escalation monitor endpoints
- Returns calls flagged as escalatory with reason and score.

Full, machine-readable API reference is maintained in API_DOCUMENTATION.md — prefer that for integration.

---

Database schema and models (authoritative excerpt & explanations)
See schema.md for full DDL. Below are key tables and field-level semantics and recommended constraints.

1) cities
- id SERIAL PRIMARY KEY
- name VARCHAR(100) NOT NULL UNIQUE
- state VARCHAR(100)
Purpose: canonical list of cities and their states used to group calls and compute regional metrics.

2) agents
- id UUID PRIMARY KEY DEFAULT gen_random_uuid()
- name VARCHAR(150) NOT NULL
- employee_id VARCHAR(50) UNIQUE
- languages TEXT[] — array of languages the agent can handle
- current_quality_score DECIMAL(5,4) DEFAULT 0.0 — aggregated 0–1
- current_sop_compliance_score DECIMAL(5,4) DEFAULT 0.0
- current_sentiment_stabilization_score DECIMAL(5,4) DEFAULT 0.0
- current_escalation_rate DECIMAL(5,4) DEFAULT 0.0
- calls_handled_total INT DEFAULT 0
- total_emergencies_count INT DEFAULT 0
- calls_handled_today / emergencies_today — daily snapshot, reset logic recommended via scheduled job
- prev_month_* — previous month snapshot used for trend comparisons
- latest_month_insight / overall_insight_text / latest_change_summary — LLM-generated text summaries
- insight_history JSONB DEFAULT '[]' — array of historical insights (structured objects)
- recent_trend_array JSONB DEFAULT '[]' — series of metric points for charting
- last_insight_generated_at TIMESTAMP
- last_updated_at TIMESTAMP DEFAULT NOW()
Notes:
- Keep insight_history bounded (retention) to avoid unbounded growth.
- Use proper indexing on employee_id and metric columns used for sorts.

3) calls
- id UUID PRIMARY KEY DEFAULT gen_random_uuid()
- agent_id UUID REFERENCES agents(id) ON DELETE SET NULL
- city_id INT REFERENCES cities(id) ON DELETE SET NULL
- customer_phone, customer_name, customer_preferred_language
- audio_url TEXT NOT NULL — S3 public or presigned URL stored
- duration_seconds INT
- call_timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
- call_context VARCHAR(30) CHECK (call_context IN (...))
- primary_issue_category VARCHAR(50)
- agent_manual_note TEXT
- processing_status VARCHAR(20) DEFAULT 'pending' CHECK (processing_status IN ('pending','transcribed','analyzed','failed'))
Notes:
- For privacy, consider hashing or removing customer_phone after analysis if retention is not required.
- Keep calls table indexed on agent_id, city_id, call_timestamp for fast aggregation.

4) call_insights
- call_id UUID PRIMARY KEY REFERENCES calls(id) ON DELETE CASCADE
- transcript TEXT
- language_spoken VARCHAR(50)
- sop_compliance_score DECIMAL(5,4) CHECK (0≤score≤1)
- other scores: sentiment_score, escalation_score, etc.
- structured_annotations JSONB — token-level annotations, timestamps, or detected policy violations
Notes:
- This table is the core output of the AI pipeline. Keep transcripts and annotations searchable with proper full-text indexes if needed.

---

Call ingestion lifecycle — implementation details & recommendations
Typical flow (as implemented across call_engestion.py + backend.py):
1. Accept multipart/form-data upload in FastAPI route.
2. Write incoming file to a secure temporary file (tmpdir), validate file type & sanitize filename.
3. Use mutagen.mp3.MP3 to obtain duration and ensure audio integrity.
4. Upload to object store (S3) with a deterministic key like `calls/{call_id}/{uuid()}.mp3`. Use server-side encryption (SSE) on S3.
5. Insert call metadata row in `calls` with `processing_status='pending'` and `audio_url` pointing to S3 (presigned or path).
6. Return call_id immediately (asynchronous pipeline recommended). Enqueue background job (via Redis queue, Celery, or direct triggered worker) to perform processing.

Best practices:
- Validate that audio duration > minimal threshold to avoid empty files.
- Implement file size limits and content-type checks.
- Use presigned S3 upload if you want to offload direct transfer from client to S3.

---

AI processing pipeline — transcription → scoring → insights (call_processing_service.py)
Core stages:
1. Fetch call metadata and audio_url.
2. Download the audio from S3 to local temporary storage.
3. (Optional) Preprocess audio: resample, convert to mono, split long calls into segments.
4. Transcription:
   - Use chosen STT engine (OpenAI Whisper, AWS Transcribe, Google Speech-to-Text, etc.).
   - Result: transcript text + timestamps per segment if supported.
5. LLM Evaluation:
   - Use LangChain/OpenAI to evaluate transcript against SOP checklists.
   - Produce:
     - sop_compliance_score (0–1)
     - per-rule pass/fail or confidence
     - sentiment_score
     - escalation_prediction (boolean/confidence)
   - Generate summary text recommendations for the agent (coaching tips).
   - Optionally compute token-level annotations to highlight where SOP deviations occurred.
6. Persist results to `call_insights` and update `calls.processing_status` to `analyzed`.
7. Update agent aggregate metrics in `agents` table (atomic transaction recommended).
8. Optionally push notifications/events for escalatory calls (email, Slack, or webhook).

Design notes:
- For reproducibility, log the prompt (or prompt template) used for the LLM evaluation (ideally redact API keys).
- Keep evaluation logic idempotent: re-processing a call should either be no-op or replace previous analysis with audit trail.
- Consider using a versioned evaluation pipeline so you can compare scores across model/prompt versions.

Prompt engineering & LLM safety:
- Use a structured prompt template that returns JSON (example: {"sop_compliance_score":0.92,"violations":[...]})
- Validate and sanitize LLM outputs before storing in DB.
- Rate limit LLM calls and add retry/backoff logic for transient API issues.

---

Storage, secrets & environment variables
Minimum environment variables (examples, set in .env for local dev):
- DATABASE_URL=postgresql://user:pass@host:5432/dbname
- OPENAI_API_KEY=sk-...
- AWS_ACCESS_KEY_ID=...
- AWS_SECRET_ACCESS_KEY=...
- S3_BUCKET_NAME=my-bucket
- S3_REGION=ap-south-1
- S3_PRESIGNED_EXPIRY=3600
- ALLOWED_ORIGINS=https://main.dhyv15pdosjd2.amplifyapp.com  (or comma-separated list)
- LOG_LEVEL=INFO
- WORKER_CONCURRENCY=4

Secrets management
- Do not store secrets in repo. Use environment variables, a secrets manager (AWS Secrets Manager / Vault), or CI/CD secret store.
- Grant least privilege to S3/IAM roles: write/get object for specific bucket prefix.

S3 best practices
- Use SSE (AES256 or KMS) for sensitive audio storage.
- Use lifecycle rules to transition older audio to Glacier or delete after retention period.
- Use presigned PUT for direct client uploads when possible.
- Make audio URLs presigned when returning to clients (avoid public audio URLs).

---

Running locally, tests & development workflow
1. Clone & create venv
2. pip install -r requirements.txt
3. Create .env with DATABASE_URL + credentials and S3/OpenAI keys
4. Start local Postgres (Docker recommended)
   docker run --name hacksmart-postgres -e POSTGRES_PASSWORD=password -e POSTGRES_USER=user -e POSTGRES_DB=hacksmart -p 5432:5432 -d postgres:15
5. Apply database schema (prefer migrations)
   - For now: run SQL in schema.md against the DB (psql or pgAdmin)
6. Run dev server:
   uvicorn backend:app --reload --port 8080
7. Use Postman or curl to exercise endpoints.

Testing
- Add unit tests for:
  - DB model behaviors (validation)
  - Ingestion flow (file validation, S3 upload stubbed)
  - Processing pipeline (mock LLM/STT)
- Use pytest and pytest-mock / responses to stub external APIs (OpenAI, S3).
- Integration tests: use a test database and local S3 emulator (e.g., MinIO).

Example quick test for ingestion (pseudo):
- Upload a small valid mp3
- Assert calls row created, processing_status == 'pending'
- Mock S3 & mutagen behavior to simulate upload/time detection

---

Deployment & scaling recommendations
Containerization:
- Build a Docker image with base python:3.11-slim, install system deps (libpq-dev, ffmpeg if audio conversion needed), pip install -r requirements.txt.
- Use Gunicorn + Uvicorn workers for production (uvicorn workers support).

Kubernetes:
- Deploy backend as a Deployment + Horizontal Pod Autoscaler.
- Use separate worker Deployment for call processing (Celery / RQ) so HTTP throughput is isolated from CPU/IO heavy AI tasks.
- Use managed Postgres (RDS / Supabase) and S3.

Autoscaling:
- Scale workers based on queue length (Redis / SQS) and CPU for model calls.
- Use OpenSearch / Elastic for logs and full-text search of transcripts if required.

Cost optimization:
- Batch LLM requests where possible; cache evaluation templates and context.
- Use smaller / cheaper LLMs for low-sensitivity checks, escalate major analysis to higher-tier models.

---

Monitoring & observability
- Metrics to emit:
  - ingestion rate, processing rate, LLM latency, STT latency
  - percentage of calls flagged as escalatory
  - database query times for heavy aggregations (leaderboard/dashboard)
- Tools:
  - Prometheus + Grafana for metrics
  - ELK or Loki for logs (structured JSON logs)
  - Sentry for exceptions
- Instrument code with:
  - structured logging (timestamp, request_id, call_id)
  - request tracing (OpenTelemetry) to follow audio download → LLM → DB update

---

Operational playbook & troubleshooting
Common issues & fixes:
- Uploads failing
  - Check S3 credentials & bucket policy
  - Confirm file content-type & size limits
- Long processing times
  - Inspect STT and LLM latency in traces; consider smaller models or chunked processing
- Incorrect scores or drift after prompt changes
  - Keep prompt and model version in DB with each analysis; enable reprocessing with old prompt for auditing
- Database deadlocks on aggregate updates
  - Use transactions and row-level locks sparingly; prefer incremental metrics and background recompute for heavy aggregations

FAQ
- Q: How to re-run analysis for a call?
  - A: Call the /api/calls/{call_id}/process endpoint or run the worker task for that call_id; ensure idempotency.
- Q: How to reset daily snapshots for agents?
  - A: Implement a cron job that shifts `calls_handled_today` -> 0 at midnight, storing snapshots as required.
- Q: How to remove PII?
  - A: Implement a purge job; consider hashing or redacting customer_phone in calls table and store hashed tokens for linking only.

---

Security considerations
- Network:
  - Restrict database access to backend IPs / VPCs.
  - Use HTTPS for all endpoints.
- Data:
  - Encrypt audio at rest and during transit.
  - Minimize retention of PII; adopt a retention policy (e.g., 6 months).
- LLM usage:
  - Be careful sending PII to third-party LLMs; redact personal identifiers if regulatory environment requires it.
- Authentication:
  - Add authentication & authorization (JWT / OAuth) for API access; currently not present in repo.
- Least privilege IAM:
  - Create dedicated IAM role for backend with limited S3 prefixes and no global admin access.

---

Suggested improvements & roadmap
Short-term (0–3 months)
- Add authentication for admin and ingestion clients.
- Implement background worker (Celery/RQ) with a retry policy and dead-letter queue.
- Add database migrations with Alembic; move away from raw DDL file for versioning.
- Unit & integration tests with CI (GitHub Actions) that run lint, format, and tests.

Medium-term (3–9 months)
- Add RAG-capable insights: store vector embeddings of transcripts for semantic search (use OpenAI embeddings or local LLM).
- Integrate Slack/webhook alerts for escalatory calls.
- Implement rate limiting and request throttling.

Long-term
- Multi-tenant support (if required)
- Auditing and model performance monitor (precision/recall on SOP detection)
- Retraining/continuous evaluation loop for LLM prompt & scoring heuristics

---

Developer & contribution guidelines
- Branching: Use feature branches per task. Open PRs against main.
- Tests: Add tests for any logic added; CI must run tests and linting.
- Style: Follow PEP8. Use black/isort for consistency.
- PR description: Motivation, design changes, security impact, and migration notes.

---

Troubleshooting checklist (quick)
- 500 errors when calling API:
  - Check application logs, stack trace (Sentry or stderr)
  - Validate DATABASE_URL and that DB is reachable
- Transcription returns empty:
  - Confirm audio is not silent; check mutagen duration
  - Check STT provider usage quotas
- LLM timeouts or 429s:
  - Implement exponential backoff; monitor quotas and increase concurrency limits carefully

---

Contacts & support
- Repo owner / maintainer: @adityachanna
- For urgent production issues: configure an “on-call” rotation and use paged alerts (Slack/SMS)

---

Appendix
- requirements.txt (core dependencies):
  - sqlalchemy
  - psycopg2-binary
  - python-dotenv
  - boto3
  - fastapi
  - uvicorn
  - python-multipart
  - pydantic
  - requests
  - mutagen
  - langchain
  - langchain-openai

- Useful file references in this repo:
  - backend.py — FastAPI routes & CORS configuration
  - call_engestion.py — ingestion logic
  - call_processing_service.py — AI evaluation orchestration
  - schema.md — canonical Postgres schema (apply to DB or migrate into Alembic)
  - API_DOCUMENTATION.md — full endpoint docs and sample responses
