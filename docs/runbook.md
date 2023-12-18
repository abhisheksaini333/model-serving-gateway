# Operating and recovering the gateway

## Start, inspect, drain

Use `docker compose up --build -d`; check `docker compose ps` and `docker compose logs --tail 100 gateway`. Readiness requires usable durable storage, Redis and an enabled backend. Liveness only means the HTTP process responds. Prometheus requires the operator bearer token; configure it through a protected token file in your monitoring system, not a committed scrape configuration.

Use the console to inspect active/queued requests, output usage and request details. Draining a backend prevents new routing while its active request finishes. Global `POST /ops/drain` also rejects pending admission and new requests. A process restart resets modes and breaker state to enabled; keep an external traffic gate closed if maintenance must continue. Operator mode changes are persisted as audit events and require the expected old mode.

`docker compose stop gateway` allows 30 seconds for cooperative shutdown. If a native call hangs, process termination is the remaining recovery mechanism. Do not advertise a freed slot while its worker is still running. After a forced stop, restart on the same data volume: incomplete records become `abandoned` with `process_restart`, and old request IDs remain protected against replay.

## Diagnose failures

| Symptom | Action |
| --- | --- |
| 429 | Inspect the tenant's configured request, concurrent and output budgets. Wait for its fixed window; avoid clearing shared Redis keys. |
| `queue_full` | Reduce client concurrency or increase a measured capacity profile. Queue size does not create model capacity. |
| `coordination_unavailable` | Restore the dedicated Redis service and verify readiness. Inference admission fails closed. |
| `ledger_unavailable` | Drain external traffic, inspect filesystem space/permissions and SQLite integrity, take a backup if readable, then restart after repair. A successful terminal result was withheld. |
| `runtime_unavailable` | Inspect the native worker; restart the process under an external traffic gate. |
| Open breaker | Inspect backend failure history. After cooldown only one probe is admitted. Do not retry a stream that already delivered text. |
| Long cancellation | A native inference step has not returned. Watch worker count before concluding that capacity is free. |
| Model hash mismatch | Preserve the unexpected artifact separately; download the pinned model into a new directory and compare provenance. Never load an unverified replacement. |

The console's settlement-failure count signals uncertain Redis refunds. A failed settlement can hold a concurrency lease until its deadline plus 30 seconds and retain tokens until the fixed window changes. Redis quota history is conservative rather than transactionally coupled to SQLite. Cache TTL is at most one hour; disabling cache prevents new reads/writes but does not erase existing keys. Redis AOF and SQLite volumes contain operational data and must be access restricted.

## Back up and restore

For a native run, take a consistent snapshot while the service is live:

```sh
python -m gateway.backup var/gateway.sqlite /secure-backups/gateway-copy.sqlite
```

For Compose:

```sh
docker compose exec gateway python -m gateway.backup /data/gateway.sqlite /tmp/gateway-copy.sqlite
docker compose cp gateway:/tmp/gateway-copy.sqlite /secure-backups/gateway-copy.sqlite
```

Choose a new filename for every snapshot. The command refuses overwrite, uses SQLite's backup API to include committed WAL content and verifies integrity. Preserve the private environment separately using your secrets process. Capture Redis data through its own persistence/backup procedures if cache/quota continuity is required; the SQLite snapshot does not include Redis.

To restore, stop gateway admission and the gateway process. Preserve the original SQLite database **and its WAL/SHM files together** in a separate recovery location. Restore the verified snapshot under the configured database path with ownership appropriate to UID 65532 for the container. Start one gateway process and verify readiness and a known request ID. In-flight work from the snapshot is marked abandoned, never rerun automatically. For a snapshot rollback, retire the former Redis namespace and configure a fresh isolated namespace to avoid mixing stale leases with rolled-back identities; this resets quotas and requires an explicit operational decision.

`docker compose down` stops this deployment and retains named volumes. Do not use `down -v` when preserving data. Keep old snapshots; do not edit database records to make a recovery appear successful.

## Deployment boundary

The checked profile binds loopback and has no public TLS, identity provider, distributed identity store or cross-process failover. Before exposing it beyond a trusted machine, provide a trusted TLS reverse proxy, credential rotation and external access control. Do not send sensitive prompts through the sample diagnostic. The local model can hallucinate, and its output is untrusted application data.
