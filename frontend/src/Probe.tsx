import React, { FormEvent, useEffect, useRef, useState } from "react";
import { request } from "./api";
import { consumeEvents } from "./stream";
const prompt =
  "Translate English to German: The little girl walks along the river every morning with her grandfather. They watch the birds and talk about the flowers in the garden. When the weather is cold, they wear warm coats and carry a basket of fresh bread.";
export default function Probe() {
  const [credential, setCredential] = useState("");
  const [text, setText] = useState("");
  const [status, setStatus] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const controller = useRef<AbortController>();
  const alive = useRef(true);
  useEffect(
    () => () => {
      alive.current = false;
      controller.current?.abort();
    },
    []
  );
  async function run(event: FormEvent) {
    event.preventDefault();
    const abort = new AbortController();
    controller.current = abort;
    const identity = crypto.randomUUID();
    setBusy(true);
    setText("");
    setError("");
    setStatus("Waiting for the first generated text…");
    let terminal = false;
    try {
      const response = await fetch("/v1/stream", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${credential}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model: "flan-small",
          prompt,
          max_new_tokens: 128,
          request_id: identity,
        }),
        signal: abort.signal,
      });
      if (!response.ok) {
        const data = await response.json();
        throw new Error(data.error?.message || "Probe failed.");
      }
      if (!response.body)
        throw new Error("Streaming is unavailable in this browser.");
      await consumeEvents(response.body, (event) => {
        if (!alive.current) return;
        if (event.type === "token") {
          setText((value) => value + (event.text || ""));
          setStatus("Generation in progress");
        }
        if (event.type === "error")
          throw new Error(event.error?.message || "Generation failed.");
        if (event.type === "result") {
          terminal = true;
          setStatus(
            `Complete · ${
              event.response?.usage.output_tokens
            } tokens · ${Math.round(event.response?.latency_ms || 0)} ms`
          );
        }
      });
      if (!terminal) throw new Error("Stream closed before a terminal result.");
    } catch (failure) {
      if (!alive.current) return;
      if (abort.signal.aborted) {
        setStatus("Client disconnected. Checking worker cleanup…");
        for (let attempt = 0; attempt < 50; attempt++) {
          try {
            const record = await request<{
              state: string;
              output_tokens: number;
            }>(credential, `/v1/requests/${identity}`);
            if (!["queued", "running"].includes(record.state)) {
              setStatus(
                `${
                  record.state === "cancelled" ? "Cancelled" : record.state
                } · ${record.output_tokens} generated tokens recorded`
              );
              break;
            }
          } catch {
            setStatus("Probe disconnected before status could be read.");
            break;
          }
          await new Promise((resolve) => window.setTimeout(resolve, 100));
        }
      } else {
        setError((failure as Error).message);
        setStatus("Probe stopped");
      }
    } finally {
      if (alive.current) setBusy(false);
      controller.current = undefined;
    }
  }
  return (
    <section className="panel probe">
      <div className="panel-heading">
        <div>
          <span className="section-number">05 / DIAGNOSTIC</span>
          <h2>Test the streaming path</h2>
        </div>
        <span className="helper">
          Fixed translation prompt · maximum 128 generated tokens
        </span>
      </div>
      <form onSubmit={run} className="probe-form">
        <div>
          <label htmlFor="probe-key">Tenant credential for probe</label>
          <input
            id="probe-key"
            type="password"
            autoComplete="off"
            value={credential}
            onChange={(event) => setCredential(event.target.value)}
            required
            disabled={busy}
          />
        </div>
        <button className="primary" disabled={busy}>
          {busy ? "Streaming…" : "Run streaming probe"}
        </button>
        {busy && (
          <button type="button" onClick={() => controller.current?.abort()}>
            Disconnect stream
          </button>
        )}
      </form>
      <p className="table-note">
        Uses tenant quota. The operator credential cannot generate model
        requests.
      </p>
      {status && (
        <p className="probe-status" role="status">
          {status}
        </p>
      )}
      {error && (
        <p role="alert" className="notice error">
          {error}
        </p>
      )}
      {text && <pre className="probe-output">{text}</pre>}
    </section>
  );
}
