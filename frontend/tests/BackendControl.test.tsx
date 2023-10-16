import React from "react";
import { afterEach, expect, test, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import BackendControl from "../src/BackendControl";
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});
const backend = {
  name: "cpu-a",
  model: "flan-small",
  revision: "original",
  active: 1,
  capacity: 1,
  mode: "enabled" as const,
  circuit: "closed",
  failures: 0,
};
test("explains a backend change and sends the expected prior mode", async () => {
  const fetcher = vi.fn(async () => ({
    ok: true,
    json: async () => ({ name: "cpu-a", mode: "draining" }),
  }));
  vi.stubGlobal("fetch", fetcher);
  const changed = vi.fn();
  render(
    <BackendControl
      backend={backend}
      credential="operator"
      onChanged={changed}
    />
  );
  fireEvent.click(screen.getByRole("button", { name: "Drain cpu-a" }));
  expect(fetcher).not.toHaveBeenCalled();
  expect(screen.getByText(/Existing generation can finish/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "Confirm drain" }));
  await waitFor(() => expect(changed).toHaveBeenCalled());
  expect(JSON.parse(fetcher.mock.calls[0][1].body)).toEqual({
    mode: "draining",
    expected_mode: "enabled",
  });
});
