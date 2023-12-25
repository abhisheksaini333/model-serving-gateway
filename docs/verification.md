# Verification and acceptance

The native CPU profile was exercised on an Apple M3 Pro host with 11 logical CPUs and 18 GiB physical memory. The Linux ARM64 container had a two-CPU quota and 2 GiB memory limit; PyTorch used two threads. Other local work shared the host. Container-visible logical CPU count is not the container's CPU quota.

The checkpoint is original `google/flan-t5-small` revision `371f99f1df1429771f01227c93bd662f5eec2480`. Its six verified artifact hashes are in [model-artifacts.json](../evidence/model-artifacts.json). The server never downloads an unpinned model during startup. The retained native smoke returned the incorrect owner “sarah”; this demonstrates why infrastructure success is separate from answer quality.

| Acceptance | Evidence | Result and boundary |
| --- | --- | --- |
| Authenticated normalized request contract | `tests/test_contracts.py`, `test_auth.py`, `test_api.py`; HTTP benchmark | Tenant derives from credentials; operator and tenant privileges separated |
| Actual HTTP inference and streaming | [Container workload](../evidence/http-benchmark-container.json), [native model smoke](../evidence/container-model-smoke.json) | Actual Transformers checkpoint; first decoded text precedes completed generation |
| Cancellation releases capacity | HTTP workload and `frontend/e2e/operator.spec.ts` | Disconnect and explicit cancellation both observe active worker before cancellation and zero after; partial usage retained |
| Queue overflow, quota and deadline | Same HTTP workload; actual Redis tests | 9/12 burst requests rejected, tenant third admission 429, short deadline 504 |
| Dependency and backend outage | Same HTTP workload | Redis container stopped and restarted; real backend disabled through operator API, then restored; both fail 503 and recover |
| Breaker, pre-output fallback and no replay after partial output | `test_breaker.py`, `test_routing.py`, `test_api.py` | Controlled adapters exercise failure timing; cooldown readiness allows a nonconsumed recovery probe. No multi-host HA claim |
| Cache and quota isolation | `test_engine.py`, `test_cache.py`, `test_redis_quota.py` | Actual Redis with controlled backend: tenant/revision/options identity, cache hit zero inference tokens, atomic quota settlement |
| Identity and process recovery | [Container restart](../evidence/container-recovery.json), `test_store.py`, `test_recovery.py` | Actual model stream interrupted by SIGKILL; same volume restarted; record abandoned, duplicate 409 |
| Ledger failure cleanup | `test_finalization.py` | Injected storage failure with real Redis: no successful terminal event, closed readiness/admission, released capacity and terminated consumer |
| Live backup | Restart report and `test_backup.py` | Integrity-checked snapshot retained 33 requests; WAL data and audit preserved; overwrite rejected |
| Prometheus and data minimization | [Actual metrics](../evidence/metrics.prom), `test_metrics.py`, API tests | Real endpoint; bounded labels, seconds units, no prompt or request-ID labels; counters reset on process restart |
| Usable operator console | [Screenshot](../evidence/operator-console.png), 3 browser journeys | Drain/enable, real probe, disconnect and actual cancellation, 390px layout, credential clearing |
| Independent installation | Hashed ARM Docker lock, `pyproject.toml`, downloader/setup tests | Nonroot native ARM image, wheel import outside source, generated Compose environment; weights external |
| Test and CI coverage | [Verification profile](../evidence/verification.json) | 73 Python tests on macOS and native Linux ARM; 7 React tests; 3 actual container browser journeys. Hosted Actions/x86 emulation not executed |

## Measurements

The normal workload sends eight serial deterministic translation requests, each capped at 128 new tokens, with cache disabled. The overload scenario sends twelve together against one inference slot and two waiting slots. The prompt, individual observations and failures are retained in the JSON reports.

| Profile | Serial success | Latency p50 / p95 | First text p50 / p95 | Generated tokens / successful request-second |
| --- | --- | --- | --- | --- |
| Native Linux ARM container | 8 / 8 | 1,171 / 1,226 ms | 76 / 243 ms | 51.7 |
| Native macOS baseline | 8 / 8 | 420 / 618 ms | 29 / 194 ms | 129.5 |

Read the [macOS baseline](../evidence/http-benchmark.json) and [container report](../evidence/http-benchmark-container.json) for exact values. These runs have different process/resource conditions and are not a controlled platform comparison. No speedup or SLA is inferred. The container report precedes a later circuit-readiness fix; final-image tests and browser journeys were rerun after that fix. Runtime source identity and final image ID are recorded in `verification.json`.

TTFT means first **nonempty decoded text**, not first internal decoder token. Token rate is total successful output tokens divided by summed successful request duration, including queue and inference time. It is not aggregate concurrent system throughput. Percentiles use nearest rank. Overload latency includes fast rejections and is therefore not a useful success-latency percentile on its own; the raw response list supports separate analysis.

No GPU, vLLM, llama.cpp/GGUF, hosted CI, public production deployment or sustained-load result is claimed. The checks prove this bounded local CPU profile and its failure handling.
