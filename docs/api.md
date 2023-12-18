# API behavior

All inference and operator endpoints require a bearer credential. `/health/live`, `/health/ready`, `/docs` and static console assets are public on the loopback deployment. `GATEWAY_TENANTS_JSON` maps credentials to tenant names and request/concurrency/output-token limits; `GATEWAY_OPERATOR_KEY` is a separate administrative credential.

| Endpoint | Credential | Result |
| --- | --- | --- |
| `POST /v1/generate` | Tenant | Completed JSON response or normalized HTTP error |
| `POST /v1/stream` | Tenant | SSE `token`, then one `result` or `error` event |
| `GET /v1/requests/{id}` | Tenant | This tenant's durable request metadata |
| `POST /v1/requests/{id}/cancel` | Tenant | Cooperative cancellation request; poll status for completion |
| `GET /ops/summary` | Operator | Platform, capacity, backend modes, usage and settlement failures |
| `GET /ops/requests?limit=50` | Operator | Most recent 1–100 request records |
| `GET /ops/audit` | Operator | Latest 100 persisted mode actions |
| `POST /ops/backends/{name}/mode` | Operator | Change mode with `{ "mode": "draining", "expected_mode": "enabled" }` |
| `POST /ops/drain` | Operator | Stop new admission and reject waiting work; active work can finish |
| `POST /ops/requests/{tenant}/{id}/cancel` | Operator | Cancel a specific active request |
| `GET /metrics` | Operator | Prometheus text exposition |

Generation fields: `model` (currently `flan-small`), nonblank `prompt` (up to 16,384 characters), optional `request_id` (1–80 identifier characters), `max_new_tokens` (1–512, default 64), `timeout_ms` (100–120,000, default 30,000) and `temperature` (0–2, default deterministic zero). The verified backend further rejects inputs beyond 512 encoder tokens. Unknown fields are rejected; body size is bounded at 128 KiB.

A result contains `request_id`, `model`, `backend`, `text`, `finish_reason`, `usage`, `cached`, `latency_ms` and `ttft_ms`. `usage` counts actual encoder input and decoder output tokens, including generated EOS where present. Cached results report zero inference tokens. TTFT is time to the first nonempty decoded text chunk; tokenizer buffering means it differs from first internal decoder token latency.

Errors have the shape `{ "error": { "code": "...", "message": "..." } }`. Important outcomes:

| HTTP status | Typical code | Caller behavior |
| --- | --- | --- |
| 401/403 | Authentication failure | Supply the correct credential class |
| 409 | `duplicate_request`, `identity_conflict`, `stale_mode` | Inspect existing state; never blindly replay |
| 413/422 | Body/contract error, `context_limit`, `output_limit` | Reduce input or correct options |
| 429 | Tenant quota/concurrency limit | Wait for capacity/window and use a new request ID |
| 499 | `cancelled` | Cancellation completed; partial output is not a success |
| 503 | `queue_full`, `unavailable`, `draining`, `coordination_unavailable`, `ledger_unavailable` | Follow the recovery runbook |
| 504 | `deadline_exceeded` | Work expired; inspect durable state before another request |

SSE sends no body before its first model event. A pre-output failure therefore retains its HTTP status. After any text is sent, HTTP status remains 200 and a later failure is an SSE `error`; consumers must require a terminal `result` to accept success. Closing the stream requests cancellation but cannot guarantee immediate preemption of a native model step.

Only observed final usage is authoritative. Abandoned requests and backend failures that could not report final usage can show zero observed tokens even though some work happened. Redis retains conservative reserved budget in ambiguous cases. Request-rate limits count admitted requests, including failed and cached requests. Output-budget refunds do not refund request count.
