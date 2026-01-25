import { expect, test } from "vitest";
import { EventDecoder } from "../src/stream";
test("parses SSE across network chunks without losing partial data", () => {
  const decoder = new EventDecoder();
  expect(decoder.push('event: token\ndata: {"type":"token","te')).toEqual([]);
  expect(
    decoder.push(
      'xt":"hello"}\n\nevent: result\ndata: {"type":"result","response":{"usage":{"output_tokens":1},"latency_ms":1}}\n\n'
    )
  ).toEqual([
    { type: "token", text: "hello" },
    { type: "result", response: {usage: {output_tokens: 1}, latency_ms: 1} },
  ]);
});
test("rejects oversized incomplete events", () => {
  const decoder = new EventDecoder();
  expect(() => decoder.push("x".repeat(131073))).toThrow(/limit/);
});
