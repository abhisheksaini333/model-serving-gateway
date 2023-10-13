import React, { FormEvent, useEffect, useRef, useState } from "react";
import { request, Summary } from "./api";
import "./style.css";

export default function App() {
  const [draft, setDraft] = useState("");
  const [key, setKey] = useState("");
  const [summary, setSummary] = useState<Summary>();
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [updated, setUpdated] = useState("");
  const generation = useRef(0);

  async function refresh(credential = key) {
    const current = ++generation.current;
    const value = await request<Summary>(credential, "/ops/summary");
    if (current === generation.current) {
      setSummary(value);
      setUpdated(new Date().toLocaleTimeString());
      setError("");
    }
  }
  async function connect(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await refresh(draft);
      setKey(draft);
      setDraft("");
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  useEffect(() => {
    if (!key) return;
    const interval = window.setInterval(() => {
      if (!document.hidden)
        refresh().catch((failure) => setError(failure.message));
    }, 5000);
    return () => {
      window.clearInterval(interval);
      generation.current++;
    };
  }, [key]);

  const tokens =
    summary?.usage.reduce((total, row) => total + row.output_tokens, 0) || 0;
  return (
    <div className="shell">
      <aside className="rail">
        <a className="brand" href="/" aria-label="Gateway home">
          <span className="brand-mark">G</span> GATEWAY
        </a>
        <div className="rail-caption">INFERENCE OPERATIONS</div>
        <div className="rail-current">
          01 <span>Control room</span>
        </div>
        <div className="rail-bottom">
          MODEL SERVING
          <br />
          <span>CPU · LOCAL RUNTIME</span>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            <span className="eyebrow">OPERATOR WORKSPACE</span>
            <h1>Keep inference moving.</h1>
          </div>
          <div className={"status " + (key ? "healthy" : "")}>
            <span className="dot" />
            {key ? "Connected" : "Awaiting connection"}
          </div>
        </header>
        {error && (
          <div role="alert" className="notice error">
            {error}
          </div>
        )}
        {!key ? (
          <section className="connect panel">
            <div className="section-number">01 / ACCESS</div>
            <h2>Connect to your gateway</h2>
            <p>
              Inspect capacity, follow requests and control backend availability
              from one console.
            </p>
            <form onSubmit={connect}>
              <label htmlFor="credential">Operator credential</label>
              <input
                id="credential"
                type="password"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                autoComplete="off"
                required
              />
              <p className="helper">
                Kept in memory for this session. Reloading clears access.
              </p>
              <button className="primary" disabled={busy}>
                {busy ? "Connecting…" : "Connect to gateway"}
              </button>
            </form>
          </section>
        ) : (
          <>
            <div className="toolbar">
              <span>Live state · refreshed {updated || "now"}</span>
              <div>
                <button
                  onClick={() =>
                    refresh().catch((failure) => setError(failure.message))
                  }
                >
                  Refresh
                </button>
                <button
                  className="quiet"
                  onClick={() => {
                    generation.current++;
                    setKey("");
                    setSummary(undefined);
                    setError("");
                  }}
                >
                  Disconnect
                </button>
              </div>
            </div>
            {summary && (
              <>
                <section className="flow" aria-label="Inference capacity">
                  <div>
                    <span className="eyebrow">WAITING</span>
                    <strong>
                      {summary.admission.queued}
                      <small> / {summary.admission.max_queue}</small>
                    </strong>
                    <span>bounded queue</span>
                  </div>
                  <div className="flow-arrow" aria-hidden="true">
                    →
                  </div>
                  <div>
                    <span className="eyebrow">RUNNING</span>
                    <strong>
                      {summary.admission.active}
                      <small> / {summary.admission.capacity}</small>
                    </strong>
                    <span>capacity in use</span>
                  </div>
                  <div className="flow-arrow" aria-hidden="true">
                    →
                  </div>
                  <div>
                    <span className="eyebrow">GENERATED</span>
                    <strong>{tokens.toLocaleString()}</strong>
                    <span>output tokens · all tenants</span>
                  </div>
                  <div className="flow-note">
                    <span className="pulse" />
                    {summary.admission.draining
                      ? "Gateway is draining"
                      : "Admission is open"}
                    <small>{summary.workers} model workers active</small>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <span className="section-number">02 / BACKENDS</span>
                      <h2>Model capacity</h2>
                    </div>
                    <span className="helper">
                      Only complete responses can be cached.
                    </span>
                  </div>
                  <div className="backend-list">
                    {summary.backends.map((backend) => (
                      <article className="backend" key={backend.name}>
                        <div className="backend-icon" aria-hidden="true">
                          ▥
                        </div>
                        <div>
                          <h3>{backend.name}</h3>
                          <span className="helper">{backend.model}</span>
                        </div>
                        <div>
                          <span className={"badge " + backend.mode}>
                            {backend.mode}
                          </span>
                          <span className="helper block">
                            Circuit {backend.circuit}
                          </span>
                        </div>
                        <div className="backend-capacity">
                          <strong>
                            {backend.active}/{backend.capacity}
                          </strong>
                          <span className="helper block">workers occupied</span>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <span className="section-number">03 / ACCOUNTING</span>
                      <h2>Tenant usage</h2>
                    </div>
                    <span className="helper">
                      Durable ledger · cached calls generate zero tokens
                    </span>
                  </div>
                  {summary.usage.length ? (
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>Tenant</th>
                            <th>Requests</th>
                            <th>Completed</th>
                            <th>Cache hits</th>
                            <th>Generated tokens</th>
                          </tr>
                        </thead>
                        <tbody>
                          {summary.usage.map((row) => (
                            <tr key={row.tenant}>
                              <td className="mono">{row.tenant}</td>
                              <td>{row.requests}</td>
                              <td>{row.completed}</td>
                              <td>{row.cache_hits}</td>
                              <td>{row.output_tokens}</td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  ) : (
                    <p className="empty">
                      No admitted requests yet. Usage appears after your first
                      inference request.
                    </p>
                  )}
                </section>
                {summary.settlement_failures > 0 && (
                  <div className="notice" role="status">
                    Some quota settlements need recovery. Review the Redis
                    recovery runbook before admitting more work.
                  </div>
                )}
              </>
            )}
          </>
        )}
        <footer>
          Bounded capacity. Observable decisions.{" "}
          <span>Model Serving Gateway</span>
        </footer>
      </main>
    </div>
  );
}
