import React, { useState } from "react";
import { Backend, request } from "./api";

export default function BackendControl({
  backend,
  credential,
  onChanged,
}: {
  backend: Backend;
  credential: string;
  onChanged: () => void | Promise<void>;
}) {
  const [pending, setPending] = useState<{
    mode: Backend["mode"];
    expected: Backend["mode"];
  }>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function apply() {
    if (!pending) return;
    setBusy(true);
    setError("");
    try {
      await request(credential, `/ops/backends/${backend.name}/mode`, {
        mode: pending.mode,
        expected_mode: pending.expected,
      });
      setPending(undefined);
      await onChanged();
    } catch (failure) {
      setError((failure as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="backend-control">
      {error && (
        <p role="alert" className="inline-error">
          {error}
        </p>
      )}
      {pending ? (
        <div className="confirmation">
          <p>
            Set <strong>{backend.name}</strong> to {pending.mode}? Existing
            generation can finish.{" "}
            {pending.mode === "enabled"
              ? "New requests will be admitted."
              : "New requests will use another available backend."}
          </p>
          <button disabled={busy} className="primary" onClick={apply}>
            {pending.mode === "draining"
              ? "Confirm drain"
              : pending.mode === "disabled"
              ? "Confirm disable"
              : "Confirm enable"}
          </button>
          <button
            disabled={busy}
            className="quiet"
            onClick={() => setPending(undefined)}
          >
            Cancel
          </button>
        </div>
      ) : (
        <div className="backend-actions">
          {backend.mode === "enabled" ? (
            <>
              <button
                onClick={() =>
                  setPending({ mode: "draining", expected: backend.mode })
                }
                aria-label={`Drain ${backend.name}`}
              >
                Drain
              </button>
              <button
                onClick={() =>
                  setPending({ mode: "disabled", expected: backend.mode })
                }
                aria-label={`Disable ${backend.name}`}
              >
                Disable
              </button>
            </>
          ) : (
            <button
              onClick={() =>
                setPending({ mode: "enabled", expected: backend.mode })
              }
              aria-label={`Enable ${backend.name}`}
            >
              Enable
            </button>
          )}
        </div>
      )}
    </div>
  );
}
