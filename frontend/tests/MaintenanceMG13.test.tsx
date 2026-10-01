import {expect,test} from "vitest";
import {consumeEvents} from "../src/stream";
const body=(value:string)=>{
 let done=false;
 return {getReader:()=>({read:async()=>{if(done)return {done:true};done=true;return {done:false,value:new TextEncoder().encode(value)};},cancel:async()=>{},releaseLock:()=>{}})} as unknown as ReadableStream<Uint8Array>;
};
test("truncated and unterminated responses are reported",async()=>{
 for(const text of ['data: {"type":"token"','data: {"type":"token","text":"x"}\n\n'])
  await expect(consumeEvents(body(text),()=>undefined)).rejects.toThrow();
});
test("a valid terminal event completes the stream",async()=>{
 await consumeEvents(body('data: {"type":"error","error":{"message":"offline"}}\n\n'),()=>undefined);
});
