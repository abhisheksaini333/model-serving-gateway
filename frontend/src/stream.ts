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
    if (this.pending.length > 131072)
      throw new Error("Stream event exceeds the size limit.");
    const blocks = this.pending.split("\n\n");
    this.pending = blocks.pop() || "";
    return blocks.filter(Boolean).map((block) => {
      const data = block
        .split("\n")
        .filter((line) => line.startsWith("data:"))
        .map((line) => line.slice(5).trimStart())
        .join("\n");
      const value = JSON.parse(data);
      if (!["token", "result", "error"].includes(value.type))
        throw new Error("Unknown stream event.");
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
