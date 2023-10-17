import React, { useEffect, useRef, useState } from "react";
import { request } from "./api";
interface Record {
  tenant: string;
  request_id: string;
  state: string;
  output_tokens: number;
  latency_ms: number | null;
  ttft_ms: number | null;
  created: number;
  error_code?: string;
  backend?: string;
  cached?: boolean;
}
const duration = (value: number | null) =>
  value === null ? "—" : `${Math.round(value)} ms`;
export default function Requests({ credential }: { credential: string }) {
  const [rows, setRows] = useState<Record[]>([]);
  const [state, setState] = useState("all");
  const [error, setError] = useState("");
  const [selected, setSelected] = useState<Record>();
  const [busy, setBusy] = useState("");
  const alive = useRef(true);
  const sequence = useRef(0);
  async function load() {
    const current = ++sequence.current;
    try {
      const values = await request<Record[]>(credential, "/ops/requests");
      if (alive.current && current === sequence.current) {
        setRows(values);
        setError("");
      }
    } catch (failure) {
      if (alive.current) setError((failure as Error).message);
    }
  }
  useEffect(() => {
    alive.current = true;
    load();
    const timer = window.setInterval(() => {
      if (!document.hidden) load();
    }, 3000);
    return () => {
      alive.current = false;
      window.clearInterval(timer);
      sequence.current++;
    };
  }, [credential]);
  async function cancel(row: Record) {
    setBusy(row.request_id);
    try {
      await request(
        credential,
        `/ops/requests/${row.tenant}/${row.request_id}/cancel`,
        {}
      );
      await load();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy("");
    }
  }
  const visible = rows.filter((row) => state === "all" || row.state === state);
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="section-number">04 / REQUESTS</span>
          <h2>Follow the work</h2>
        </div>
        <div className="request-filter">
          <label htmlFor="request-state">Filter request state</label>
          <select
            id="request-state"
            value={state}
            onChange={(event) => setState(event.target.value)}
          >
            {[
              "all",
              "queued",
              "running",
              "completed",
              "failed",
              "cancelled",
              "expired",
              "abandoned",
            ].map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      <div className="table-scroll request-table">
        <table>
          <thead>
            <tr>
              <th>Request / tenant</th>
              <th>State</th>
              <th>First text</th>
              <th>Latency</th>
              <th>Tokens</th>
              <th>Action</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((row) => (
              <tr key={row.tenant + ":" + row.request_id}>
                <td>
                  <button
                    className="link mono"
                    title={row.request_id}
                    onClick={() => setSelected(row)}
                  >
                    {row.request_id.length > 14
                      ? row.request_id.slice(0, 14) + "…"
                      : row.request_id}
                  </button>
                  <span className="helper block">{row.tenant}</span>
                </td>
                <td>
                  <span className={"badge " + row.state}>{row.state}</span>
                </td>
                <td>{duration(row.ttft_ms)}</td>
                <td>{duration(row.latency_ms)}</td>
                <td>{row.output_tokens}</td>
                <td>
                  {["queued", "running"].includes(row.state) ? (
                    <button
                      aria-label={`Cancel ${row.request_id}`}
                      disabled={busy === row.request_id}
                      onClick={() => cancel(row)}
                    >
                      Cancel
                    </button>
                  ) : (
                    <span className="helper">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {!visible.length && <p className="empty">No requests in this state.</p>}
      {selected && (
        <div className="request-detail">
          <div>
            <strong>Request details</strong>
            <button className="quiet" onClick={() => setSelected(undefined)}>
              Close details
            </button>
          </div>
          <dl>
            <dt>Request ID</dt>
            <dd className="mono">{selected.request_id}</dd>
            <dt>Tenant</dt>
            <dd>{selected.tenant}</dd>
            <dt>Backend</dt>
            <dd>{selected.backend || "Not assigned"}</dd>
            <dt>Outcome</dt>
            <dd>{selected.error_code || selected.state}</dd>
            <dt>Created</dt>
            <dd>{new Date(selected.created * 1000).toLocaleString()}</dd>
          </dl>
          <p className="helper">
            The ledger stores usage and state. Prompt and response text are not
            retained.
          </p>
        </div>
      )}
      <p className="table-note">
        Most recent 50 requests · token counts are recorded when generation
        stops
      </p>
    </section>
  );
}
