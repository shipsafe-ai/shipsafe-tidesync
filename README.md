# TideSync

**Your pipeline succeeded. Your data is still wrong.**

Every data pipeline has a control plane that reports success and a destination
that holds the truth — and the two disagree more often than anyone admits. Your
sync tool says "completed, 1.2M rows, green checkmark." The warehouse table it
wrote to last updated four hours ago. Nobody gets paged, because nothing
*failed*. The dashboards downstream just quietly serve stale numbers until
someone notices a report is wrong.

TideSync is an autonomous agent that catches this exact silent failure mode:
**the pipeline says it succeeded, but the data is stale.** It reads pipeline
status from the control plane, queries the destination directly for the real
freshness of the data, and uses Gemini to reason about the contradiction
between the two — then surfaces a confidence-scored verdict, an SLA breach
projection, and a recommended fix for a human to approve.

## The contradiction that is the product

TideSync triangulates two independent sources of truth and reasons about where
they disagree:

```
Control plane says:   "sync succeeded at 09:14, 1.2M rows"   (Fivetran, via MCP)
Destination says:     "MAX(_fivetran_synced) = 06:45,
                       lag = 4h 41m"                          (BigQuery, direct query)
Gemini concludes:     "Silent staleness. Control plane is
                       green but data is 4h41m old. SLA
                       breach in ~2h 15m. Confidence: high."
```

A successful sync status is not evidence that data is fresh. Only the
destination knows that. TideSync is the agent that checks.

## How it works

TideSync is a multi-agent system. A sequential orchestrator runs five
specialists plus a two-layer adversarial critic, and never executes a
remediation without explicit human approval.

```
Trigger (POST /run or Fivetran sync_end webhook)
   │
   ▼
SyncSentinel ─── control-plane truth (list_connections, get_connection_details)
   │             via the official Fivetran MCP server, REST fallback
   ▼
DataDoctor ───── data truth (BigQuery: MAX(_fivetran_synced),
   │             TIMESTAMP_DIFF lag_seconds, row counts, null-rate drift)
   ▼
Critic · Layer 1 ─ deterministic regex prompt-injection pre-screen over every
   │               field; aborts the run if any value looks like an instruction
   ▼
ImpactMapper ─── Gemini (Vertex AI) reasons across both sources, emits a
   │             structured verdict: is_stale, lag, SLA-breach ETA, confidence,
   │             cost recommendation
   ▼
Critic · Layer 2 ─ Gemini adversarially challenges the staleness verdict:
   │               UPHOLD or CHALLENGE, with full chain-of-reasoning. Does the
   │               evidence justify the call? Did the input try to manipulate it?
   ▼
BriefingAgent ── Gemini synthesizes a plain-language reliability briefing
   │             (runs in the background; does not block the verdict)
   ▼
Human Approval Gate ── if stale, /run returns awaiting_approval + a token.
                       Nothing is remediated automatically.
   │
   ▼
RecoveryAgent ── triggers a resync ONLY after POST /approve/{token}, and only
                 when FIVETRAN_ALLOW_WRITES=true. Approval-gated, never auto-run.
```

Every Gemini call is Vertex AI with the model read from config — never
hardcoded. Contradiction is flagged when the destination's `lag_seconds`
exceeds the staleness threshold (`STALE_THRESHOLD_SECONDS`, default `3600` =
1 hour) while the control plane still reports success.

## Real Model Context Protocol integration (Fivetran)

TideSync does not just call a REST API. It spawns the **official open-source
`fivetran/fivetran-mcp` server** (cloned into the container image at
`/opt/fivetran-mcp`) as a subprocess and talks to it over **stdio using the
Model Context Protocol**. Control-plane reads (`list_connections`,
`get_connection_details`) go **MCP-first**, with a direct Fivetran REST call as
a fallback so a live demo never depends on the subprocess succeeding.

- The full Fivetran MCP tool surface is exposed — verify it live with
  `GET /mcp/tools`, which returns `connected: true` plus the complete tool list
  (77 tools as deployed).
- `USE_FIVETRAN_MCP=false` disables the MCP path entirely and falls back to REST.
- The spawned MCP server is launched read-only (`FIVETRAN_ALLOW_WRITES=false`);
  writes never flow through it.

> TideSync is demonstrated on maritime logistics (the ShipSafe Hormuz crisis
> scenario), but works for **any data pipeline** — finance period closes, ML
> feature stores, clinical record syncs, analytics warehouses. The control-plane
> vs. data-truth contradiction is universal. Connect your own Fivetran
> connection and BigQuery dataset and it works unchanged; nothing about it is
> shipping-specific.

## Prompt-injection defense

Pipeline metadata, connector names, and table contents are user-influenced
data, so TideSync treats all of it as **data, never instructions**:

- **Layer 1 — deterministic:** a regex pre-screen flags injection patterns
  (`ignore previous`, `new instructions`, `system:`, etc.) in every field and
  aborts the run before any LLM sees a manipulated value.
- **Layer 2 — adversarial Gemini critic:** the verdict is independently
  challenged by a second Gemini call instructed to reason against it and to set
  `injection_suspected` if any field reads like a command. The critic returns
  `UPHOLD` or `CHALLENGE` with explicit reasoning; on any error it fails safe to
  `CHALLENGE` and defers to a human.
- **No auto-execution:** every remediation is gated behind a human approval
  token plus an explicit write flag.

## Endpoints

The agent (API) and dashboard are deployed as **two separate Cloud Run
services**: `tidesync` (this API) and `tidesync-dashboard` (the Next.js UI).

API base: `https://tidesync-336382452417.us-central1.run.app`

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/health` | Liveness — `{"status":"ok"}` |
| `POST` | `/run` | Full contradiction analysis. Returns `complete`, or `awaiting_approval` + `approval_token` if stale |
| `POST` | `/approve/{token}` | Human approval gate — triggers the gated RecoveryAgent resync |
| `GET` | `/connections` | Live control-plane connection reports (SyncSentinel) |
| `GET` | `/freshness` | BigQuery data-truth freshness (DataDoctor); `?connection_id=` for one |
| `GET` | `/mcp/tools` | Live proof of the real Fivetran MCP integration (server, transport, tool list) |
| `GET` | `/briefing` | Latest Gemini reliability briefing |
| `POST` | `/webhooks/fivetran` | HMAC-verified Fivetran `sync_end` / `connection_failure` receiver |

The dashboard renders the contradiction panel, staleness indicator, SLA
projection, connection health, and morning briefing. (Reasoning is produced as
structured output and rendered after the run completes — the verdict is not
streamed token by token.)

## Install & run

TideSync ships as the npm package **`shipsafe-tidesync`**:

```bash
npx shipsafe-tidesync health   # check the deployed agent is reachable
npx shipsafe-tidesync demo      # run the Hormuz crisis scenario against /run
npx shipsafe-tidesync init      # print agent URL + connection instructions
```

To run against your own data, provide a Fivetran connection and a BigQuery
destination dataset, and store credentials in GCP Secret Manager
(`FIVETRAN_APIKEY`, `FIVETRAN_APISECRET`, `WEBHOOK_SECRET`). Required config:
`GCP_PROJECT`, `GEMINI_MODEL`, `BQ_DATASET`. The agent runs on Google Cloud Run.

## Tech

- **Agent brain:** Python on Google ADK (sequential orchestrator + specialists +
  critic), deployed to Cloud Run.
- **Reasoning:** Gemini on Vertex AI (model from config), structured output only.
- **Control plane:** Fivetran via the official `fivetran/fivetran-mcp` MCP
  server over stdio, with REST fallback.
- **Data truth:** Google BigQuery, queried directly.
- **Dashboard:** Next.js 14 + Tailwind, separate Cloud Run service.
- **CLI:** Node, published as `shipsafe-tidesync`.
- **Secrets:** GCP Secret Manager. Nothing hardcoded.

---

## Part of the ShipSafe fleet

TideSync is one of six independently deployable AI operations agents built for
the Google Cloud Rapid Agent Hackathon. Each solves a distinct class of
production problem and deploys with a single command:

| Agent | Watches for |
|---|---|
| CargoDB | Data that quietly disagrees across sources |
| RouteForge | Unsafe changes to critical algorithms/code |
| VoyageBlack | Undocumented incidents |
| **TideSync** | **Pipelines that "succeed" while data goes stale** |
| NaviGuard | AI quality regressions |
| AgentOps | The agents themselves (fleet observability) |

## License

MIT — see [LICENSE](./LICENSE).
