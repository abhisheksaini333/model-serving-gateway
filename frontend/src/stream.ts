export interface StreamEvent {
  type: "token" | "result" | "error";
  text?: string;
  response?: { usage: { output_tokens: number }; latency_ms: number };
  error?: { message: string };
}
export class EventDecoder {
  private pending = "";
  push(chunk: string): StreamEvent[] {
    this.pending += chunk;
    const blocks = this.pending.split(/\r?\n\r?\n/);
    this.pending = blocks.pop() || "";
    if (this.pending.length > 131072 || blocks.some((block) => block.length > 131072))
      throw new Error("Stream event exceeds the size limit.");
    return blocks.filter((block) => block.split(/\r?\n/).some((line) => line.startsWith("data:"))).map((block) => {
      const data = block
        .split(/\r?\n/)
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      const value = JSON.parse(data);
      if (!value || !["token", "result", "error"].includes(value.type))
        throw new Error("Unknown stream event.");
      if (value.type === "token" && typeof value.text !== "string")
        throw new Error("Invalid token event.");
      if (value.type === "error" && typeof value.error?.message !== "string")
        throw new Error("Invalid error event.");
      if (value.type === "result" && (!Number.isInteger(value.response?.usage?.output_tokens) || value.response.usage.output_tokens < 0 || !Number.isFinite(value.response?.latency_ms) || value.response.latency_ms < 0))
        throw new Error("Invalid result event.");
      return value as StreamEvent;
    });
  }
}
export async function consumeEvents(
  body: ReadableStream<Uint8Array>,
  receive: (event: StreamEvent) => void
) {
  const reader = body.getReader();
  const text = new TextDecoder();
  const events = new EventDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      for (const event of events.push(text.decode(value, { stream: true })))
        receive(event);
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
