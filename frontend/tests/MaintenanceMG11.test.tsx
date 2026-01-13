import {expect,test} from "vitest";
import {EventDecoder} from "../src/stream";
test("SSE comments and split CRLF framing are accepted",()=>{
 const d=new EventDecoder();
 expect(d.push(": heartbeat\r\n\r")).toEqual([]);
 expect(d.push('\ndata: {"type":"token","text":"hi"}\r\n\r')).toEqual([]);
 expect(d.push("\n")).toEqual([{type:"token",text:"hi"}]);
});
