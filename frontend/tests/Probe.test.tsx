import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import Probe from "../src/Probe";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
test("runs a fixed diagnostic and presents streamed text with measured usage", async () => {
  vi.stubGlobal("crypto", { randomUUID: () => "probe-one" });
  const data = new TextEncoder().encode(
    'event: token\ndata: {"type":"token","text":"Das Haus"}\n\nevent: result\ndata: {"type":"result","response":{"usage":{"output_tokens":3},"latency_ms":42}}\n\n'
  );
  let consumed = false;
  const reader = {
    read: async () => {
      if (consumed) return { done: true };
      consumed = true;
      return { done: false, value: data };
    },
    cancel: async () => {},
    releaseLock: () => {},
  };
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: true, body: { getReader: () => reader } }))
  );
  render(<Probe />);
  fireEvent.change(screen.getByLabelText("Tenant credential for probe"), {
    target: { value: "tenant-key" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Run streaming probe" }));
  expect(await screen.findByText("Das Haus")).toBeTruthy();
  expect(await screen.findByText(/Complete · 3 tokens/)).toBeTruthy();
});
