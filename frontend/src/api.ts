export interface Backend {
  name: string;
  model: string;
  revision: string;
  active: number;
  capacity: number;
  mode: "enabled" | "draining" | "disabled";
  circuit: string;
  failures: number;
}
export interface Summary {
  admission: {
    active: number;
    queued: number;
    capacity: number;
    max_queue: number;
    draining: boolean;
  };
  backends: Backend[];
  usage: {
    tenant: string;
    requests: number;
    output_tokens: number;
    completed: number;
    cache_hits: number;
  }[];
  workers: number;
  settlement_failures: number;
}
export async function request<T>(
  key: string,
  path: string,
  body?: unknown
): Promise<T> {
  const decoded = decodeURIComponent(path.split("?")[0]);
  if (!/^\/(ops|v1)\//.test(path) || !/^\/(ops|v1)\//.test(decoded) || decoded.includes("\\") || decoded.split("/").some((part) => part === "." || part === ".."))
    throw new Error("Invalid API destination.");
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: {
        Authorization: `Bearer ${key}`,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
      redirect: "error",
    });
    let result;
    try { result = await response.json(); }
    catch { throw new Error(`The service returned an unreadable response (${response.status}).`); }
    if (!response.ok)
      throw new Error(
        result.error?.message || `Request failed (${response.status}).`
      );
    return result as T;
  } finally {
    window.clearTimeout(timer);
  }
}
