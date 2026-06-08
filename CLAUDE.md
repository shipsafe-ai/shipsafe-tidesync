# CLAUDE.md — shipsafe-tidesync (Fivetran track)

This is the TideSync submission repo. Read this file fully before
writing any code. Then read PARTNER-INTEGRATION.md §4.

---

## What TideSync does

TideSync catches the "sync OK but data stale" contradiction —
the silent failure mode where Fivetran reports a successful sync
but the destination data is hours old. Two-source agent: Fivetran
MCP for pipeline status, BigQuery direct queries for data truth.

The contradiction that IS the product:
```
Fivetran MCP says:  "sync succeeded at 09:14, 1.2M rows"
BigQuery says:      "MAX(_fivetran_synced) = 06:45, lag = 4h 41m"
Gemini concludes:   "silent staleness — SLA breach in ~2h 15m"
```

---

## Status: DEPLOYED ✅ (as of 2026-06-08)

**Live URL**: `https://tidesync-336382452417.us-central1.run.app`

Verified endpoints:
- `GET /health` → `{"status":"ok","version":"0.1.0"}`
- `GET /connections` → live Fivetran connector list
- `GET /freshness?connection_id=exorbitant_motioned` → real BQ lag
- `POST /run` → full Gemini contradiction analysis
- `POST /webhooks/fivetran` → HMAC-verified webhook receiver

Fivetran connector: `exorbitant_motioned` (Google Sheets → BigQuery)
BQ dataset: `hormuz_port_arrivals`, table: `arrivals` (50 rows)
Account webhook: `widowed_hunt` (fires on `sync_end` + `connection_failure`)
14-day trial started: 2026-06-07, expires ~2026-06-21

---

## Agent specialists

| Specialist | File | Job |
|---|---|---|
| SyncSentinel | specialists/sync_sentinel.py | Fivetran: list_connections, get_connection_details |
| DataDoctor | specialists/data_doctor.py | BigQuery: MAX(_fivetran_synced), row counts, null-rate drift |
| ImpactMapper | specialists/impact_mapper.py | Gemini: contradiction detection + SLA projection |
| RecoveryAgent | specialists/recovery_agent.py | Fivetran writes: run_connection_setup_tests, sync_connection |
| BriefingAgent | specialists/briefing_agent.py | Gemini: morning briefing synthesis |
| Critic | critic.py | Prompt-injection check (runs BEFORE ImpactMapper) |

Orchestrator: `agent/orchestrator.py` (ADK SequentialAgent)
API: `api/main.py` (FastAPI, webhook receiver at `/webhooks/fivetran`)

---

## Fivetran integration

Auth: HTTP Basic (`base64(apikey:apisecret)`). NOT Bearer.

CRITICAL API behaviors:
- **No `/connections/{id}/state` endpoint** — returns 405. State is inside
  `GET /connections/{id}` response at `data.status` (a dict, not a string).
  Extract `data.status.setup_state` for simple status string.
- **Skip paused + fivetran_log connectors** when iterating for data analysis.
  `evasive_endearing` is the system Fivetran log connector — no schemas, paused.
- **Webhook registration sends unsigned ping** to validate URL. Accept requests
  with no `X-Fivetran-Signature` header as liveness checks (return 200).

Two-service-account BigQuery model:
- Fivetran SA `g-healing-servile@fivetran-production.iam.gserviceaccount.com`:
  OWNER on `hormuz_port_arrivals` dataset, objectAdmin on `shipsafe-fivetran-staging`
- TideSync SA `tidesync-sa@shipsafe-ai.iam.gserviceaccount.com`:
  `bigquery.dataViewer`, `bigquery.jobUser`, `secretmanager.secretAccessor`, `aiplatform.user`

Demo trigger: delete named range `arrivals_data` from Google Sheet or clear all data.
After ≤60 min next sync, Fivetran reports success but BQ lag > 3600s → `is_stale: true`.

---

## Secrets

All in Secret Manager (`shipsafe-ai` project):
- `FIVETRAN_APIKEY` ✅
- `FIVETRAN_APISECRET` ✅
- `WEBHOOK_SECRET` ✅ (used for HMAC-SHA256 webhook verification)
- BigQuery: no secret — Cloud Run SA IAM via `tidesync-sa`

---

## Cloud Run env vars

```
GCP_PROJECT=shipsafe-ai
GEMINI_MODEL=gemini-2.5-flash
BQ_DATASET=hormuz_port_arrivals
FIVETRAN_ALLOW_WRITES=true
STALE_THRESHOLD_SECONDS=3600
TIDESYNC_PUBLIC_URL=https://tidesync-336382452417.us-central1.run.app
```

Deploy: `docker buildx build --platform linux/amd64 --push` (ARM64 rejected by Cloud Run)
Update env: always `--update-env-vars`, never `--set-env-vars` (set-env-vars wipes all vars)

---

## Gemini / Vertex AI

Do NOT use `response_schema` with a raw dict — Vertex AI SDK rejects it
(`KeyError: 'object'`, nullable union types also fail).

Use this pattern instead:
```python
response = model.generate_content(
    prompt_with_schema_in_text,
    generation_config={"response_mime_type": "application/json"},
)
return json.loads(response.text)
```

Include the JSON schema in the prompt text. Do not pass `response_schema`.

---

## Cross-cutting rules (all 9 apply)

1. ALL LLM calls use Gemini via Vertex AI ONLY. Never OpenAI.

2. Agent brains are Python ADK on Cloud Run. No low-code Agent Builder.

3. Deep MCP integration — Fivetran MCP (50+ tools) + BigQuery direct.

4. All deployments target Google Cloud Run only.

5. Every credential in GCP Secret Manager. Nothing hardcoded.

6. TDD always. Test file exists and FAILS before implementation.
   Run: `python -m pytest tests/ -v` (31 tests, all passing)

7. Gemini model from config, never hardcoded. (`config.GEMINI_MODEL`)

8. CROSS-SUBMISSION ISOLATION. TideSync is fully self-contained.
   No calls to other submissions.

9. PROMPT-INJECTION DEFENSE. Pipeline data flows as structured dict.
   Critic runs BEFORE ImpactMapper. Human approval gate before any resync.
   `FIVETRAN_ALLOW_WRITES` must be `true` for RecoveryAgent writes.

Full canonical rules: https://github.com/shipsafe-ai/shipsafe-shared/blob/main/CLAUDE.md
Full partner spec: https://github.com/shipsafe-ai/shipsafe-shared/blob/main/docs/PARTNER-INTEGRATION.md
