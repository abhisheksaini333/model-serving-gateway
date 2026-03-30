import {expect,test} from "vitest";
import {consumeEvents} from "../src/stream";
const body=(value:string)=>new ReadableStream<Uint8Array>({start(c){c.enqueue(new TextEncoder().encode(value));c.close();}});
test("truncated and unterminated responses are reported",async()=>{
 for(const text of ['data: {"type":"token"','data: {"type":"token","text":"x"}\n\n'])
  await expect(consumeEvents(body(text),()=>undefined)).rejects.toThrow();
});
test("a valid terminal event completes the stream",async()=>{
 await consumeEvents(body('data: {"type":"error","error":{"message":"offline"}}\n\n'),()=>undefined);
});
