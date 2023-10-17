import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import Requests from "../src/Requests";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
test("filters terminal requests and cancels only an active request", async () => {
  const rows = [
    {
      tenant: "alpha",
      request_id: "first",
      state: "completed",
      output_tokens: 5,
      latency_ms: 12,
      ttft_ms: 4,
      created: 1,
    },
    {
      tenant: "beta",
      request_id: "active",
      state: "running",
      output_tokens: 0,
      latency_ms: null,
      ttft_ms: null,
      created: 2,
    },
  ];
  const fetcher = vi.fn(async (path: string) => ({
    ok: true,
    json: async () =>
      path.endsWith("/cancel") ? { cancellation_requested: true } : rows,
  }));
  vi.stubGlobal("fetch", fetcher);
  render(<Requests credential="operator" />);
  await screen.findByText("first");
  fireEvent.change(screen.getByLabelText("Filter request state"), {
    target: { value: "running" },
  });
  expect(screen.queryByText("first")).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: "Cancel active" }));
  await waitFor(() =>
    expect(
      fetcher.mock.calls.some(
        (call) => call[0] === "/ops/requests/beta/active/cancel"
      )
    ).toBe(true)
  );
});
