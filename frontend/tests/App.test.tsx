import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import App from "../src/App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const summary = {
  admission: {
    active: 1,
    queued: 2,
    capacity: 1,
    max_queue: 4,
    draining: false,
  },
  backends: [
    {
      name: "cpu-a",
      model: "flan-small",
      revision: "original",
      active: 1,
      capacity: 1,
      mode: "enabled",
      circuit: "closed",
      failures: 0,
    },
  ],
  usage: [
    {
      tenant: "alpha",
      requests: 5,
      output_tokens: 12,
      completed: 4,
      cache_hits: 1,
    },
  ],
  workers: 1,
  settlement_failures: 0,
};

test("connects with an in-memory operator credential and shows real capacity", async () => {
  const fetcher = vi.fn(async (path: string) => ({
    ok: true,
    json: async () => (path === "/ops/summary" ? summary : []),
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<App />);
  fireEvent.change(screen.getByLabelText("Operator credential"), {
    target: { value: "operator-key" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Connect to gateway" }));
  await screen.findByText("cpu-a");
  expect(screen.getByText("flan-small")).toBeTruthy();
  expect(screen.getAllByText("12")).toHaveLength(2);
  expect(localStorage.length).toBe(0);
  expect(fetcher.mock.calls[0][1].headers.Authorization).toBe(
    "Bearer operator-key"
  );
  fireEvent.click(screen.getByRole("button", { name: "Disconnect" }));
  expect(
    screen.getByLabelText("Operator credential").getAttribute("value")
  ).toBe("");
});

test("shows authentication failure without pretending to have loaded data", async () => {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({
      ok: false,
      status: 401,
      json: async () => ({
        error: { message: "A valid bearer credential is required." },
      }),
    }))
  );
  render(<App />);
  fireEvent.change(screen.getByLabelText("Operator credential"), {
    target: { value: "bad-key" },
  });
  fireEvent.click(screen.getByRole("button", { name: "Connect to gateway" }));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByText("cpu-a")).toBeNull();
});
